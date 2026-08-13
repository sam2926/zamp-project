# <span style="color:#D6336C">API contract</span>

The interface between `api/` (FastAPI) and `web/` (React). **Build the UI against this — it
is stable.** The pipeline behind it is being implemented in parallel; endpoints return
realistic mock data until it lands, then swap in behind the same shapes.

Base URL in development: `http://localhost:8000`. In production the API and the built
frontend are served from the same origin, so all paths are relative — never hardcode a host.

---

## <span style="color:#2E7D32">Core concepts the UI must express</span>

| concept | meaning |
|---|---|
| **field** | one extracted value — `vendor_name`, `amount_total_gross`, … |
| **confidence** | 0–1, calibrated. 0.95 means right 95% of the time |
| **status** | `ok` · `review` · `repaired` · `missing` |
| **box** | where on the page the value came from, normalised 0–1 |
| **line item** | a repeating row; fields group by `line_item_id` |

**The product thesis, in UI terms:** every value shows how much to trust it, and points at
where it came from. A screen that shows values without confidence or provenance misses the
entire point.

---

## <span style="color:#2E7D32">Endpoints</span>

### <span style="color:#1565C0">POST /api/documents</span>

Upload a PDF. `multipart/form-data`, field name `file`.

```json
{ "id": "a3f9c2", "filename": "invoice.pdf", "status": "processing", "pages": 2 }
```

`413` if over 20MB · `415` if not a PDF · `422` if the PDF is unreadable.

### <span style="color:#1565C0">GET /api/documents/{id}</span>

The whole result. Poll until `status` is `done`.

```json
{
  "id": "a3f9c2",
  "filename": "invoice.pdf",
  "status": "done",
  "pages": 1,
  "layout": { "known": true, "seen_count": 47, "used_template": true },
  "processing": { "ms": 340, "model_called": false },
  "fields": [
    {
      "name": "vendor_name",
      "value": "ACME SUPPLY CO",
      "confidence": 0.97,
      "status": "ok",
      "page": 0,
      "box": [0.09, 0.12, 0.41, 0.15]
    },
    {
      "name": "amount_total_gross",
      "value": "1290.00",
      "confidence": 0.62,
      "status": "review",
      "page": 0,
      "box": [0.78, 0.34, 0.88, 0.36],
      "reason": "line items sum to 1190.00, not 1290.00"
    },
    {
      "name": "address__postcode",
      "value": "OL3 5DE",
      "original": "0L3 5DE",
      "confidence": 0.88,
      "status": "repaired",
      "page": 0,
      "box": [0.09, 0.18, 0.22, 0.20],
      "reason": "postcodes cannot begin with a digit; one substitution fixes it"
    }
  ],
  "line_items": [
    {
      "id": 1,
      "fields": [
        { "name": "description", "value": "Widget, 40mm", "confidence": 0.94,
          "status": "ok", "page": 0, "box": [0.10, 0.52, 0.38, 0.54] },
        { "name": "quantity", "value": "12", "confidence": 0.91,
          "status": "ok", "page": 0, "box": [0.42, 0.52, 0.46, 0.54] }
      ]
    }
  ],
  "validation": [
    { "rule": "line_items_sum_to_total", "passed": false,
      "detail": "Σ line items 1190.00 ≠ total 1290.00",
      "suspect_fields": ["amount_total_gross"] },
    { "rule": "net_plus_tax_equals_gross", "passed": true }
  ]
}
```

**`status` values on the document:** `processing` · `done` · `failed`.
When `failed`, a top-level `"error"` string explains why in plain language.

**Notes for the UI**

- `box` is `[left, top, right, bottom]` as fractions of the page. Multiply by the rendered
  image size to overlay it.
- `reason` is present on anything not `ok`. **Always show it** — an unexplained flag is
  worse than no flag.
- `original` appears only on `repaired`, so the UI can show what was changed.
- `layout.known` and `processing.model_called` drive the "this cost nothing to process"
  signal. Worth surfacing.

### <span style="color:#1565C0">GET /api/documents/{id}/page/{n}</span>

PNG of page `n`, zero-indexed. For the document viewer. `?width=1200` optional.

### <span style="color:#1565C0">PATCH /api/documents/{id}/fields/{name}</span>

A human correction from the review screen.

```json
{ "value": "1190.00" }
```

Returns the updated field. Sets `status` to `ok` and `confidence` to `1.0`, and records the
correction so the same mistake is not repeated.

### <span style="color:#1565C0">GET /api/documents</span>

The review queue. Query params: `status`, `needs_review` (bool), `limit`, `offset`,
`sort` (`uploaded` · `confidence`).

```json
{
  "total": 1500,
  "items": [
    { "id": "a3f9c2", "filename": "invoice.pdf", "uploaded": "2026-08-11T14:02:00Z",
      "vendor": "ACME SUPPLY CO", "total": "1290.00",
      "fields_ok": 17, "fields_review": 2, "min_confidence": 0.62 }
  ]
}
```

### <span style="color:#1565C0">GET /api/stats</span>

Powers the dashboard. This is where the project proves itself.

```json
{
  "documents": 1500,
  "deterministic_coverage": 0.81,
  "auto_accepted": 0.74,
  "calibration": [
    { "bucket": "0.9–1.0", "predicted": 0.95, "actual": 0.94, "n": 8200 },
    { "bucket": "0.7–0.9", "predicted": 0.80, "actual": 0.78, "n": 1400 }
  ],
  "per_field": [
    { "field": "vendor_name", "n": 338, "f1": 0.91 },
    { "field": "amount_total_gross", "n": 331, "f1": 0.88 }
  ],
  "by_layout": { "seen": { "f1": 0.93 }, "unseen": { "f1": 0.71 } }
}
```

**`by_layout` is the honest number** — how it performs on formats never seen before. Give it
prominence rather than burying it.

---

## <span style="color:#2E7D32">Rules for the UI</span>

- **Never show a value without its confidence.** That is the product.
- **Never show a flag without its reason.**
- **Review is per field, not per document.** If 17 fields are fine and 2 are shaky, the
  reviewer sees 2.
- **Clicking a field highlights its box on the page.** This is the moment that sells it.
- **Empty and error states matter** — first visit, upload failed, unreadable PDF, nothing
  flagged. Design them, do not leave them blank.
