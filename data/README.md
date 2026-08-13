# Data

This directory is **gitignored**. Nothing here is committed — datasets are large and
should be fetched from their original sources. This file explains how.

---

## `kleister/` — Kleister-Charity (74 MB as fetched)

2,778 annual financial reports from British charities, mostly scanned. Labeled with
8 fields. Published SOTA: 83.57% F1.

```bash
git clone --single-branch -b master https://github.com/applicaai/kleister-charity data/kleister
```

What you get:

| path | size | contents |
|---|---|---|
| `train/in.tsv.xz` | 21 MB | OCR text, 1,729 docs |
| `dev-0/in.tsv.xz` | 6.1 MB | OCR text, 440 docs |
| `test-A/in.tsv.xz` | 8.4 MB | OCR text, 609 docs (no labels — held-out) |
| `train/expected.tsv` | 448 KB | ground truth |
| `dev-0/expected.tsv` | 116 KB | ground truth |
| `documents/` | — | **git-annex pointers, not real PDFs** |

`in.tsv.xz` columns: `filename`, `keys`, `text_djvu`, `text_tesseract`, `text_textract`,
`text_best`. Three OCR engines plus the authors' pick of the best.

To pull the actual PDFs (~12 GB, needs `git-annex`):

```bash
cd data/kleister && ./annex-get-all-from-s3.sh
```

Source: documents and labels both from the UK Charity Commission
(https://www.gov.uk/government/organisations/charity-commission).

---

## `propublica-990-api/` — IRS Form 990 API responses (1.1 MB)

Sampling output from the ProPublica Nonprofit Explorer API. 5 keyword searches → 60 small
nonprofits → their full filing records.

Kept as evidence for one finding: across those 60 orgs, **563 filings have structured
data and 319 don't** — 36% invisible to any query.

The API is free and needs no auth:

```bash
curl "https://projects.propublica.org/nonprofits/api/v2/organizations/142007220.json"
```

**The PDFs are not obtainable.** `robots.txt` disallows `/nonprofits/download-filing*`,
and the endpoint returns Cloudflare 403s. IRS bulk downloads are XML only. This is why
990s were not chosen as the spine.

---

## DocILE — not fetched

6.7k annotated business documents (invoices), 100k synthetic, ~1M unlabeled.
Gated: request access at https://docile.rossum.ai/ to get a token, then:

```bash
./download_dataset.sh TOKEN labeled-trainval data/docile --unzip
```

Only `labeled-trainval` is worth pulling. Skip `synthetic` and `unlabeled` (94 chunks).

**Check the terms before building on it** — the repo's MIT licence covers the code, not
the data. Dataset terms reference processing of personal data for scientific research,
which may not cover a publicly deployed demo.
