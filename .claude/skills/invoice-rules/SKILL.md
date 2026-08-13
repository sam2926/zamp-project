---
name: invoice-rules
description: The deterministic validation rules for extracted invoice data — arithmetic identities that must hold, how to localise which value broke them, format checks, and single-candidate repair. Use when validating extraction output, building the checking layer, computing confidence, or deciding whether a cached template has gone stale.
---

# Deterministic validation

Rules that never consult a model. When arithmetic disagrees with an extraction, **arithmetic
wins** — it cannot hallucinate.

These run on **every field of every document**, both the template path and the model path,
regardless of how confident anything upstream was. Confidence and validity are separate
questions: "do our readers agree?" and "is this answer legal?" A value can pass one and fail
the other.

## The arithmetic identities

```
quantity × unit_price        = line_amount          (per line item)
Σ line_amount                = amount_total_net     (subtotal)
amount_total_net + amount_total_tax = amount_total_gross
amount_total_gross − amount_paid    = amount_due
amount_total_net × tax_rate  = amount_total_tax
```

Field names map to DocILE types: `line_item_quantity`, `line_item_unit_price_gross`,
`line_item_amount_gross`, `amount_total_net`, `amount_total_tax`, `amount_total_gross`,
`amount_paid`, `amount_due`, `tax_detail_rate`.

**Tolerances.** Compare with a small epsilon — rounding on tax lines is normal. Do not
demand exact equality on anything involving a percentage.

**Not every invoice populates every field.** `amount_total_net` appears on 838 documents,
`amount_total_gross` on 5,966. A rule whose inputs are absent is *skipped*, not *failed*.
Never turn a missing field into a validation error.

## Localising the error

The identities do more than detect — they point.

- If 9 of 10 line items sum correctly and adding the 10th breaks the subtotal, **the 10th
  line is the bad read.**
- If every line is individually consistent (`qty × price = amount`) but the subtotal is
  wrong, the error is in the subtotal, not the lines.
- If the subtotal and tax are right but the gross is wrong, only the gross needs rechecking.

Feed the localised field back to step 8a for a narrow retry — re-ask about the one value,
never reprocess the document.

## Format checks

| field | rule |
|---|---|
| dates | parse to a real date; not in the future; issue date ≤ due date |
| amounts | numeric after stripping currency symbols and separators |
| `iban` | country prefix, length, mod-97 check |
| `bic` | 8 or 11 characters, correct shape |
| tax IDs | per-country format where known |
| `document_id` | non-empty; flag exact duplicates across documents — possible double payment |

## Magnitude sanity

OCR digit errors usually shift a number by a factor of ten — a dropped or invented digit.
So an order-of-magnitude gap between related fields is a strong signal:

- `amount_due` more than ~10× `amount_total_gross`
- a single line item exceeding the invoice total
- a quantity in the thousands against a unit price in the thousands

These are warnings, not hard failures. Real invoices do occasionally look strange.

## Repair, when there is exactly one candidate

Some constraints are tight enough to fix rather than flag. Search single-character
substitutions over OCR-confusable pairs — `0↔O`, `1↔l↔I`, `5↔S`, `8↔B`, `2↔Z`, `6↔G` — and
if **exactly one** substitution satisfies the constraint, apply it and mark the value as
repaired.

If two or more candidates satisfy it, do not guess. Flag it for review.

Repaired values are never treated as equal to clean ones — they carry the repair in their
provenance so a reviewer can see what was changed and why.

## Stale template detection

A cached template that starts failing these checks means **the vendor redesigned their
invoice**, not that the maths is wrong.

The cache is an accelerator, never an authority. On repeated validation failure for a
layout: evict the template, send the document down the model path, relearn. This is what
stops a stale cache silently returning wrong numbers quickly.
