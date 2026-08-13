---
name: eval
description: How this project measures extraction quality — per-field scoring rather than one average, repeat-layout versus unseen-layout splits, confidence calibration curves, and deterministic coverage. Use whenever reporting accuracy, comparing approaches, building an evaluation harness, or deciding whether a change actually helped.
---

# How we measure

## The rule that governs everything

**Score on `val` only. Never tune against it.**

`train` (3,512 invoices) is for building. `val` (338) is the honest number. If a threshold,
prompt or rule was chosen by looking at `val` results, the number stops meaning anything —
we have 916 layouts and 519 singletons, so it is very easy to accidentally fit the layouts
we looked at rather than learn to read invoices.

## Never report one averaged accuracy

The field distribution is lopsided — `vendor_name` appears 7,354 times, `iban` 5. A single
average is dominated by a handful of common fields and hides every failure.

**Always report per field**, with the sample count beside it:

| field | n | precision | recall | F1 |
|---|---|---|---|---|

**Fields with n < 30 are not measurable.** Say so explicitly rather than printing a
meaningless 100% or 0%.

## The four numbers that matter

**1 · Per-field F1 on `val`.** The baseline quality measure.

**2 · Repeat layout vs unseen layout.** Split `val` by whether its `cluster_id` was seen in
`train`. Report both:

```
seen layouts    F1 = ...
unseen layouts  F1 = ...
```

The second number is the real one — it says what happens when a new vendor arrives. Most
systems only publish the first.

**3 · Calibration.** Bucket every predicted field by its confidence score, then measure
actual accuracy inside each bucket. Plot it.

- Calibrated means when it says 90%, it is right ~90% of the time.
- A flat line means the confidence is decoration and the architecture that produced it
  failed.
- Report the reliability curve, not just a single "average confidence".

**4 · Deterministic coverage.** The share of documents processed with **no model call at
all**. This is the architectural claim of the project — that the model teaches layouts
rather than reading documents — so it must be measured, and it should climb as more layouts
are learned.

## Baselines to beat

Anything clever must beat the dumb version, or it gets dropped:

1. **Floor:** single OCR reading → one model pass → extract. No agreement, no validation,
   no templates.
2. **External:** DocILE publishes baseline results for KILE and LIR tracks (RoBERTa,
   LayoutLMv3, DETR). Compare where the task definitions line up.

## Scoring mechanics

- **Normalise before comparing.** Labels are normalised; pages are not. `1290.00` versus
  `£1,290.00` is a match. Dates compare as parsed dates, not strings.
- **Watch for coincidental matches.** A 3-page invoice contains many numbers. Finding the
  digits *somewhere* is not the same as identifying the right field — score against the
  annotated field, not a substring search over the page.
- **Line items score as sets, not strings.** A row is correct when its fields are correct
  *and* grouped under the right `line_item_id`. Getting the values right but the grouping
  wrong is a failure.

## Reporting honestly

- State what was held out and when the split was fixed.
- Report failures alongside successes — the unseen-layout number, the fields that don't
  work, the documents that broke.
- If a number came from `train` rather than `val`, label it as such.
