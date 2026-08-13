---
name: docile
description: Facts about the DocILE invoice dataset used by this project — where files live, split sizes, the 55-field schema, the tax-invoice filter, layout clusters, and how to load annotations and OCR. Use whenever reading, filtering, counting or sampling the dataset, or when answering questions about what data is available.
---

# The DocILE dataset, as used in this project

## Location

`data/docile/` — gitignored. See `data/README.md` to refetch.

```
data/docile/
  pdfs/<id>.pdf           the scan
  ocr/<id>.json           precomputed OCR (single engine)
  annotations/<id>.json   ground truth
  train.json val.json test.json trainval.json    arrays of document ids
```

Every document has all three files. 6,680 documents total.

## Splits

| split | docs | annotations | use |
|---|---|---|---|
| train | 5,180 | yes | build and fit |
| val | 500 | yes | honest score — never tune against this |
| test | 1,000 | **empty files** | blind; only the benchmark organisers can score it |

`trainval` = train ∪ val (5,680). No overlap between any of the three.

**The test annotations exist but contain zero extractions.** Do not try to score against
them. Its metadata is also stripped — `document_type`, `source`, `language` are all `null`,
so it cannot be filtered by category.

## This project uses tax invoices only

| split | all types | tax invoices |
|---|---|---|
| train | 5,180 | **3,512** |
| val | 500 | **338** |

Filter on `metadata.document_type == "tax_invoice"`.

Other types present (dropped): 1,440 orders · 128 purchase orders · 116 receipts ·
75 sales orders · 29 proformas · 24 credit notes · 12 utility bills · 6 debit notes.

**Held aside as an out-of-distribution test:** the 107 orders and 21 receipts in `val`.

## Annotation schema

```json
{
  "field_extractions":     [ {bbox, fieldtype, page, text} ],
  "line_item_extractions": [ {bbox, fieldtype, page, text, line_item_id} ],
  "line_item_headers":     [ ... ],
  "metadata":              { page_count, page_sizes_at_200dpi, cluster_id,
                             currency, document_type, language,
                             original_filename, page_to_table_grid, source }
}
```

- `bbox` is `[left, top, right, bottom]`, **normalised 0–1**, not pixels.
- `page` is 0-indexed.
- Line items group by `line_item_id`.
- **`metadata` is nested.** `json.load(f)["metadata"]["document_type"]` — reading
  `document_type` off the root returns `None` and silently gives wrong counts.

## 55 field types

**36 document-level.** Most common: `vendor_name` (7,354), `vendor_address` (6,634),
`date_issue` (6,214), `customer_billing_name` (6,142), `document_id` (6,141),
`amount_due` (6,125), `amount_total_gross` (5,966).

**19 line-item**, all prefixed `line_item_`. Most common: `date` (32,405),
`description` (28,617), `amount_gross` (23,734), `quantity` (22,993),
`unit_price_gross` (19,324).

**The distribution is severely lopsided** — `vendor_name` appears 7,354 times, `iban` 5
times. Roughly 12 fields carry the corpus; 20+ appear in under 500 documents. Never report
one averaged accuracy number: it hides everything. See the `eval` skill.

## Layouts

`metadata.cluster_id` groups documents sharing a layout. Across the 3,850 tax invoices:

- **916 distinct layouts**
- **519 appear exactly once**
- top 51 layouts (6%) cover 50% of invoices; top 272 (30%) cover 80%

This is ground truth for layout grouping — use it to evaluate our own fingerprinting rather
than assuming it works.

## Document characteristics

Sampled 400 PDFs directly:

| | share |
|---|---|
| image-only, no text layer | 34% |
| image + text layer | 52% |
| text-only | 14% |

Sources: 3,035 public inspection files, 2,645 UCSF litigation archive scans.
Pages: 5,001 one-page · 1,323 two-page · 356 three-page. All English.
Currency: 4,453 USD, 1,191 other, small counts of GBP/EUR/JPY.

## Not downloaded, deliberately

- `synthetic` — 100,000 generated documents. The project rejects synthetic data.
- `unlabeled` — ~932,000 documents across 94 chunks, for pretraining. Out of scope.
