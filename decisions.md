# <span style="color:#D6336C">Decisions</span>

## <span style="color:#2E7D32">Problem statement selection</span>

### <span style="color:#1565C0">Why did I pick "turn messy documents into structured data" over the other two?</span>

**<span style="color:#B8860B">1 · I picked a problem with an objective ground truth.</span>**

- Documents → structured data has a correct answer for every field; accuracy is a number I can report.
- "Learn a user's process by watching" and "conversational agent" are graded on judgement like, _did it learn the task_, _was the conversation good_ and I would be the one marking my own work.
- Every decision in this document is a measurement. That is only honest where the truth exists independently of me.

**<span style="color:#B8860B">2 · It is a real industry problem a community is actively trying to crack.</span>**

- Document extraction is an actively worked problem, research groups and companies compete to push accuracy on exactly this task.
- That gives me an external bar to measure against, like an exam with a known passing mark, rather than a task I set and grade myself.
- And it is a problem people genuinely need solved, finance teams still key these documents in by hand, so the work is real rather than a demo.

**<span style="color:#B8860B">3 · It has a genuinely hard sub-problem to go deep on.</span>**

- Most invoices arrive in a layout never seen before, 916 layouts across the set and 519 of them appearing exactly once, so anything that needs per-vendor setup breaks the moment a new one lands.
- A third of documents carry no text layer and many are degraded scans, so a field's position on the page is never fixed.
- The hard part I went at: pull the right field off a page whose layout is new, at a fraction of the token cost, and know when the answer is shaky, by learning where a kind of value tends to sit rather than where it sat last time.

**<span style="color:#B8860B">4 · What I passed on, deliberately.</span>**

- The conversational agent is the flattering demo, a model wrapper photographs well and hides how thin it is underneath. I took the measurable problem over the photogenic one.
- "Learn by watching" is the most novel, but in five days its success is unfalsifiable; I could not have told you honestly whether it worked.
- Even so, a trace of it lives in what I built: the system learns each client's documents from their own labelled examples and tightens as corrections come back. It is one capability inside the pipeline, not the ground it stands on, and on its own it would need far more training, runs and tuning before I would trust it to stand alone.

## <span style="color:#2E7D32">Data</span>

### <span style="color:#1565C0">Why did I choose the data that I chose?</span>

**<span style="color:#B8860B">1 · I ruled out synthetic data before comparing anything.</span>**

- With generated data you are both attacker and defender, you cannot discover a failure mode you never thought to simulate.
- Ground truth by construction means every accuracy number is self-graded.
- This eliminated DocILE's own 100,000 synthetic documents too. I took only the real ones.

**<span style="color:#B8860B">2 · Kleister-Charity was the strongest contender, and I measured it before rejecting it.</span>**

- It ships **three independent OCR engines per document**, so I could test a hypothesis before committing to any dataset.
- On 1,729 documents, **no engine wins**: textract takes the money fields, tesseract the ID fields, djvu nothing. The union of all three beats every individual engine on every field — and **their own precomputed "best" column is worse than the union on all five.**
- **That result shaped the architecture I actually built.** The pipeline reads every page several ways instead of picking an engine. A measurement on the dataset I rejected determined the design of the one I chose.
- Rejected as the spine: 8 flat fields, no bounding boxes, and charity reports sit one domain hop from finance operations.

**<span style="color:#B8860B">3 · DocILE won on four things.</span>**

- **It is actually invoices.** The domain finance operations lives in, not one hop away.
- **The schema is relational.** 55 field types; 80% of documents carry line items, one carries 110. Eight flat fields give a query layer nothing to work with.
- **Bounding boxes ship with it.** Click a number, see the source region — achievable, not reverse-engineered.
- **It is verifiably hard.** I sampled 400 PDFs: **34% contain no text layer at all.** 2,645 documents come from the UCSF litigation archive — degraded material I could not have faked credibly.
- **Accepted in exchange:** one OCR engine instead of three, so I generate the disagreement signal myself — which the deployed product needed regardless, since a stranger's upload was never in anyone's precomputed file. And a gated research licence instead of open government data.

### <span style="color:#1565C0">What did I scope in?</span>

**<span style="color:#B8860B">1 · I narrowed to one document type: tax invoices.</span>**

- 3,512 to build on, 338 to score. Dropped orders, POs, receipts, proformas, credit notes, utility bills, debit notes.
- **Sharper rules.** Line items summing to the total holds on an invoice, not a utility bill. Mixing types would have forced me to weaken the rule for everything.
- **Sharper product.** "Invoice processing" is bought. "Document processing" is researched.
- Most discarded types were unmeasurable anyway — 6 debit notes, 12 utility bills.
- **Kept for free:** 107 orders and 21 receipts held aside as an out-of-distribution test. Real AP inboxes get non-invoices; now I can say what happens when one arrives.

**<span style="color:#B8860B">2 · I chose layout variety over structural uniformity, deliberately.</span>**

- 3,850 invoices span **916 layouts. 519 appear exactly once.** A handful of vendors invoice constantly; a long tail invoiced once.
- **A uniform dataset would have let me build something that already exists and already fails.** Configure-per-layout OCR works until a new vendor appears, then needs a human to reconfigure it. That is the problem, not the solution.
- So nothing in my pipeline assumes where a field sits. It reads each page several ways, checks the arithmetic, and flags disagreement, none of which cares about layout.
- The distribution then splits the work honestly: 6% of layouts carry half the volume and reward caching; the 519 one-offs must work from scratch, every time.
- **I report accuracy separately for repeat layouts and unseen ones.** Most systems only publish the first number.

## <span style="color:#2E7D32">Architecture</span>

### <span style="color:#1565C0">How did I decide to process each document?</span>

**<span style="color:#B8860B">1 · I decided the LLM would not be the runtime engine.</span>**

- Calling a model per document is expensive, slow, and non-reproducible — and cost would scale with invoice volume forever. That defeats the purpose of a system that is supposed to learn.
- So I inverted it: **deterministic extraction is the primary path, the model is the exception.**
- **The model is a teacher, not a worker.** It runs once per _new layout_ to map where the fields live. A deterministic extractor then serves every future document of that layout, and the model never sees it again.
- Cost therefore scales with **how many new vendors you meet**, not how many invoices you process. 2,000 invoices a month from 300 known vendors costs roughly 20 model calls, not 2,000.
- **The constraint I accepted:** 519 of 916 layouts appear exactly once. There is no template for a layout you have never seen, so ~15–20% of documents will always need a cold read. The model path shrinks; it never disappears.
- **Consequence — a metric worth reporting:** _deterministic coverage_, the share of documents processed with no model call at all. It should climb as the system meets more vendors. Most systems never publish this because most systems call a model every time.

### <span style="color:#1565C0">How did I split the data for measurement?</span>

**<span style="color:#B8860B">1 · Why carve a dev slice out of train when train and val already exist?</span>**

- **Train tells me nothing.** Templates learned from documents 1–3,500 will always work on documents 1–3,500 — those are the practice questions I studied from.
- **"Build on train, check val" spends val.** It gets looked at once for the template learner, once for the confidence model, and once after every disappointing result. Each look is a small adjustment fitted to val; ten cycles in it is no longer held out, and the headline number is quietly inflated.
- **So 400 of the 3,512 train documents become `dev`** — a practice exam, retaken as often as I like. Costs nothing, and it keeps the one number I publish genuinely untouched.

```
train  →  the textbook I study from
dev    →  a practice exam, retaken as often as I like
val    →  the real exam, sat once
```

**<span style="color:#B8860B">2 · Why is dev cut two ways rather than one?</span>**

- Because there are two different questions, and one split cannot answer both.
- **Hold out random documents** → does the template work on a new invoice from a vendor we know?
- **Hold out entire layouts** → does anything work on a vendor we have never seen?
- **A random split alone hides the second completely** — every held-out document still has its layout learned from its siblings.
- The layout-held-out number is the honest one, and the one most systems never publish.

### <span style="color:#1565C0">How did I decide to deploy it?</span>

**<span style="color:#B8860B">1 · Hugging Face Spaces on Docker, not Vercel or Render.</span>**

- docTR pulls in torch. The container is ~2.5GB and needs real RAM.
- That rules out Vercel and Netlify (serverless size limits) and Render's free tier — 512MB, where torch will not even load.
- HF Spaces gives 16GB RAM and 50GB disk free, with no credit card and a public URL. Fly.io is the fallback.
- **The constraint drove the choice.** Picking a host first and discovering the model does not fit is how a demo dies on submission day.

**<span style="color:#B8860B">2 · One container serving both API and frontend, not two deployments.</span>**

- FastAPI serves the React build as static files from the same origin.
- No CORS configuration, no second deploy pipeline, no environment variables pointing two services at each other — three failure modes removed rather than debugged.
- Cost: frontend and backend redeploy together. Acceptable at this size; wrong at scale.
- **A single URL is also the deliverable.** The brief asks for a working solution someone can test, not an integration exercise for the reader.

### <span style="color:#1565C0">How did I split the data for building and testing?</span>

**<span style="color:#B8860B">1 · I cut a dev slice out of train, rather than checking against val each time.</span>**

- Measuring on the data I built from tells me nothing — templates learned from 3,500 documents will obviously work on those 3,500.
- The obvious alternative, _build on train and check val_, fails quietly: that check happens once per component and once per fix after each disappointing result. Every look is a small adjustment fitted to val, and after ten cycles the headline number is inflated.
- So: **train is the textbook, dev is a practice exam I can retake freely, val is the real exam, sat once.** 400 documents cost nothing and keep the published number honest.

**<span style="color:#B8860B">2 · The slice is cut two ways, because there are two different questions.</span>**

- **Random documents held out** — does a template work on a new invoice from a vendor we already know?
- **Entire layouts held out** — does anything work on a vendor we have never seen?
- The second is the honest number, and the one most systems never publish. A random split alone hides it entirely, because every held-out document still had its layout learned from its siblings.

### <span style="color:#1565C0">How did I decide where on the page to look for a field?</span>

**<span style="color:#B8860B">1 · I started with per-layout templates: learn where each field sat, then read that spot.</span>**

- Fingerprint the layout, group labelled documents by it, record the median box per field, read that box on new documents.
- Reasonable on paper, and it is what most commercial systems do.

**<span style="color:#B8860B">2 · Fixing the obvious bugs took it from 16% to 69% on documents it had already seen — and 31% on new ones.</span>**

- Reading order was scrambling words: sorting by a rounded `y` merged adjacent lines and re-sorted across both, turning _"50 Cambridge Street"_ into _"500 Street Cambridge"_. **16% → 57%.**
- A whole-page alignment against the layout's reference words added **+5pp**; per-field anchoring measured _worse_ and was retired.
- Read tolerance swept from 0.000 to 0.018 — tight won, because a generous box swallows the row above and returns two values instead of one.

**<span style="color:#B8860B">3 · The measurement that killed it: fields move 4–5 line heights between invoices of the same layout.</span>**

|                   | median drift | p90   |
| ----------------- | ------------ | ----- |
| all layouts       | 0.044        | 0.342 |
| born-digital only | 0.057        | 0.095 |

- A text line is ~0.012 of page height, so the median field sits **four lines away** from where it was stored.
- No tolerance absorbs that without swallowing neighbouring rows — which the padding sweep showed directly, accuracy falling off on both sides.
- **x drifts as much as y** (0.038 against 0.044), so this is not line spill. The whole content block sits differently: different scan crops and scales, and layouts that group similar-but-not-identical forms.

**<span style="color:#B8860B">4 · A pure PDF text extractor did not rescue it, which proved the failure was positional and not textual.</span>**

- Ran the full learn-and-apply loop on PyMuPDF's exact text and exact coordinates instead of OCR: **28.1%**, against docTR's 31.5%.
- 91% of ground-truth values are recoverable from the text either way. **We could read the page; we were aiming at the wrong part of it.**
- Also measured: the text layer baked into 59% of documents is stale OCR from a scanning product and is **10 points worse** than modern OCR. Ignore it.

**<span style="color:#B8860B">5 · Layout retrieval was silently mismatching a fifth of documents until I added a margin test.</span>**

- Pair-level precision of 98% answered _"are these two the same layout?"_ Retrieval asks _"which of 722 layouts is this?"_ — and small per-pair error compounds across every candidate.
- **19% of documents were being matched to a different vendor's template.** Confidently wrong values, the exact failure the design was supposed to avoid.
- Fixed by requiring the best match to beat the runner-up by 2×: wrong matches fell to **3%**, at the cost of matching less often. Failing to match is cheap — the model handles it. Matching the wrong vendor is not.

**<span style="color:#B8860B">6 · So I stopped asking "which pixel" and started asking "which neighbourhood".</span>**

- Same data, different question. Build a 50×50 grid over the page and count, across 3,142 documents, which cells each field lands in.
- A field's _exact_ position is unstable. Its _region_ is not — it is consistent across 722 different layouts.

| field                 | page area holding 80% | at 90% |
| --------------------- | --------------------- | ------ |
| customer_billing_name | 4.2%                  | 6.9%   |
| date_issue            | 7.6%                  | 12.1%  |
| vendor_address        | 8.7%                  | 13.5%  |
| amount_total_gross    | 11.2%                 | 16.0%  |
| amount_due            | 11.6%                 | 16.7%  |

- Measured on 150 held-out documents: sending only `customer_billing_name`'s region cuts the prompt from **339 tokens to 38 — an 89% reduction — while the answer is still inside the region 91% of the time.**
- **The heat map is not an extractor.** It does not read the value; it decides what the model is allowed to see. That is why it survives drift where a template does not.

**<span style="color:#B8860B">7 · I narrowed the schema from 55 fields to the five that appear on nearly every invoice.</span>**

- `customer_billing_name` 97% · `amount_due` 95% · `date_issue` 95% · `amount_total_gross` 95% · `vendor_address` 91%. After these, coverage falls off a cliff.
- These five are what an AP team actually needs: who it is for, how much, when, and from whom.
- Reporting per-field accuracy on fields with five examples is noise dressed as measurement. **Better to be measurably good at five things than unmeasurably vague about 55.**

**<span style="color:#B8860B">8 · I switched from ragged cell-sets to rectangles, which measured better as well as being simpler.</span>**

- The first version kept the hottest cells, whatever shape they formed. Those sets have holes, and a field box spanning a hole falls outside.
- A rectangle is solid, so anything within its bounds is contained. Same coverage target, better result: **containment on val rose from 54.9% to 68.9% at the 80% setting, and 79.8% to 87.6% at 95%.**
- Computed as the smallest axis-aligned rectangle holding the target share of the field's mass, over a 50×50 grid.

**<span style="color:#B8860B">9 · I count every cell a field's box touches, not the cell under its centre.</span>**

- Marking centres builds a region the field's own text spills out of — the model would receive a crop with the value half cut off.
- Correcting this also corrected the measurement: "is the centre inside?" flattered the result. The honest test is whether the **whole box** is inside, and it is the test every number above now uses.

**<span style="color:#B8860B">10 · The fallback sends the whole page, not the unsearched remainder.</span>**

- Sending only the complement is cheaper and was tempting. It breaks on fields straddling the boundary: half the value sits in the crop, half in the remainder, and neither call sees a complete answer.
- So a miss costs crop + full page. That is the price of never returning a truncated value.

**<span style="color:#B8860B">11 · Crop size is chosen per field, because the economics differ per field.</span>**

- `vendor_address` at the 95% setting needs 71% of the page and costs **106% of naive** — more than simply sending the document. It stays at the 80% setting.
- `customer_billing_name` at 95% costs 39%. Same mechanism, opposite conclusion.
- **Cost is measured in words, not page area.** A tall thin rectangle over the totals block covers 41% of the page but only 34% of the words, because most of what it spans is margin.

**<span style="color:#B8860B">12 · Final configuration, validated on 338 documents the regions never saw.</span>**

| field                   | rect | % of page | % of words | found | cost |
| ----------------------- | ---- | --------- | ---------- | ----- | ---- |
| `customer_billing_name` | 95%  | 20.9%     | 31.4%      | 92.0% | 39%  |
| `amount_total_gross`    | 95%  | 40.9%     | 33.6%      | 86.6% | 47%  |
| `date_issue`            | 95%  | 33.4%     | 41.6%      | 91.1% | 50%  |
| `amount_due`            | 95%  | 51.6%     | 46.5%      | 88.0% | 59%  |
| `vendor_address`        | 80%  | 25.2%     | 27.4%      | 76.7% | 51%  |

**≈49% of naive cost at ≈87% containment.** Train and val agree across every column, so the regions describe invoices rather than the particular documents that built them.

**<span style="color:#B8860B">13 · No API key ships with this repo.</span>**

- Anyone running it supplies their own. The repo carries configuration and the system prompt, not a credential.
- A committed key is found by scrapers within minutes, and shipping one would be billing the author for every stranger's usage.
- Everything except the model call runs without one: OCR, layout matching, region cropping, validation and confidence are all local.

### <span style="color:#1565C0">How did I decide what format to send the model?</span>

**<span style="color:#B8860B">1 · Five payload formats, one field, one whole page, one prompt — only the format changed.</span>**

| format                       | accuracy  | tokens  |
| ---------------------------- | --------- | ------- |
| flat text — lines, no coords | **35.5%** | 24,431  |
| region crop                  | 29.0%     | 18,977  |
| JSON, words only, no coords  | 10.8%     | 32,156  |
| JSON `[word, x, y]`          | 26.9%     | 77,248  |
| full OCR JSON + layout hints | 21.5%     | 270,249 |
| full OCR JSON, no hints      | 32.3%     | 270,249 |

**<span style="color:#B8860B">2 · Flat text won and I cut every coordinate-bearing format.</span>** 35.5% at 24k tokens against `[word, x, y]`'s 26.9% at 77k — coordinates tripled the cost and lost accuracy.

**<span style="color:#B8860B">3 · Line breaks are worth 25 points.</span>** Words-only is flat text minus the newlines — same words, same order — and it collapses 35.5% → 10.8%. Delete the line structure and a two-column invoice interleaves into nonsense.

**<span style="color:#B8860B">4 · Why flat text works: the word is the ruler.</span>** `rows()` groups words with `|Δy| < 0.7 × the word's own height`. A model handed bare coordinates has no ruler, and merges lines 0.0156 apart when the true line height is 0.0146.

### <span style="color:#1565C0">Was it the coordinates or my prompt?</span>

**<span style="color:#B8860B">1 · I first concluded coordinates make the model worse. I was measuring my prompt.</span>** Removing my layout hints took the _same_ JSON payload 21.5% → 32.3%, fixing 14 documents and breaking 4.

**<span style="color:#B8860B">2 · The hint caused its own worst failures.</span>** It said _"words close together in both directions form a block"_ — which is exactly what glued street addresses onto company names.

**<span style="color:#B8860B">3 · The rule I took from it.</span>** When an experiment fails, check the instruction is not the variable before blaming the subject.

### <span style="color:#1565C0">How big should the crop be?</span>

**<span style="color:#B8860B">1 · I predicted the wider region would keep more captions and win. It lost.</span>**

|                    | 95% region           | 80% region              |
| ------------------ | -------------------- | ----------------------- |
| area               | 51.6% of page        | **25.8%**               |
| accuracy           | 80.0%                | **83.5%**               |
| tokens vs baseline | 98%                  | **82%**                 |
| crop answered      | 44/85, 97.7% correct | 32/85, **100% correct** |

**<span style="color:#B8860B">2 · The tighter rectangle falls back more but answers near-flawlessly.</span>** 62% fallback vs 48%, yet the crops that do answer are 100% correct.

**<span style="color:#B8860B">3 · Why: tightening removed distractors, not context.</span>** The 95% rectangle starts at x=0.36 and sweeps in line-item amounts and subtotals — up to 121 money-shaped tokens to choose between. The 80% starts at x=0.66, on the totals block.

**<span style="color:#B8860B">4 · Corollary — the value and its caption travel together.</span>** When the crop contains `TOTAL DUE` the amount is read right 98% of the time. Next: learn the region from value + label boxes, not the value alone.

### <span style="color:#1565C0">What do I trust as a confidence signal?</span>

**<span style="color:#B8860B">1 · Not the hand-set weights.</span>** `0.55 × ocr + 0.45 × heat` flagged 84 of 85 documents for review, 43 of them correct — noise.

**<span style="color:#B8860B">2 · "Did the value land in its expected region" separates 99% from 65%.</span>** 102/103 correct when the crop answered, 123/188 when it fell back. Free to compute, measured not invented.

**<span style="color:#B8860B">3 · So containment is the primary signal, and the weighted score is retired until it is fit rather than guessed.</span>**

### <span style="color:#1565C0">One field to demo — which, and why?</span>

**<span style="color:#B8860B">1 · `amount_due`, not `customer_billing_name`.</span>** An amount is one token with an unmistakable caption. A billing name carries genuine annotator ambiguity — attention line in or out? — and OCR damage, so a large share of its failures are unwinnable as scored.

**<span style="color:#B8860B">2 · The gap is not subtle.</span>** `amount_due`'s whole-page baseline is 73.5% on 291 documents; the billing name's is 35.5% on 93.

---

## <span style="color:#2E7D32">Measurements</span>

Every table produced while deciding the above, in the order they were made.

**<span style="color:#B8860B">1 · Per-engine OCR recall on Kleister.</span>** Five fields × four text sources over 1,729 documents. Showed no engine wins and the union beats all of them — the result that made the pipeline read every page several ways rather than pick one engine. _(Decided the multi-reader architecture, before any dataset was chosen.)_

**<span style="color:#B8860B">2 · Fingerprint threshold sweep.</span>** Precision, recall and F1 across thresholds 0.01–0.50 on train, then reported once on val. Chose 0.03; val F1 0.956. _(Later superseded by the retrieval test below.)_

**<span style="color:#B8860B">3 · Signature overlap distributions.</span>** Same-layout pairs share a median of 43 words out of 175; different-layout pairs share 0, with p90 at 0.008. Showed the threshold sits in a wide empty valley rather than being fragile.

**<span style="color:#B8860B">4 · Layout retrieval accuracy.</span>** Right / wrong / no-match across dev_seen, dev_unseen and val. Exposed that **19% of documents matched the wrong vendor's template** — invisible in the pair-level number. Fixed by a 2× margin test, dropping wrong matches to 3%.

**<span style="color:#B8860B">5 · Template read-tolerance sweep.</span>** Padding 0.000–0.018 with and without page-shift correction. Peaked at 0.002 with shift; accuracy fell away on both sides, showing no tolerance can absorb the drift.

**<span style="color:#B8860B">6 · Template failure breakdown.</span>** Correct / no rule / wrong region / box empty / partial. Showed 60% of failures were **missing rules**, not bad ones — the lever was coverage, not precision.

**<span style="color:#B8860B">7 · Field drift within a layout.</span>** Median 0.044 of page height against a 0.012 line height, and x drifting as much as y. The measurement that ended the template approach.

**<span style="color:#B8860B">8 · docTR against PyMuPDF, full pipeline.</span>** 31.5% vs 28.1%. Proved the failure was positional rather than textual — exact coordinates did not help.

**<span style="color:#B8860B">9 · Field frequency across 3,850 invoices.</span>** `customer_billing_name` 97% down to `payment_terms` 49%. Chose the five-field scope.

**<span style="color:#B8860B">10 · Heat map coverage, cells then rectangles, train then val.</span>** The final tables above. Chose the crop configuration.

**<span style="color:#B8860B">11 · Live end-to-end `amount_due`, all 291 val.</span>** 77.3% at 86% of baseline tokens — better accuracy _and_ cheaper. Re-checked on the 206 documents that took no part in choosing the configuration: 70.9% → 74.8%, no selection effect. _(The headline result.)_

**<span style="color:#B8860B">12 · Five-format input comparison.</span>** 93 documents, one field, only the payload format varied. Flat text 35.5% at 24k tokens beat coordinate JSON 26.9% at 77k. _(Chose flat text.)_

**<span style="color:#B8860B">13 · Layout-hint removal.</span>** Same JSON payload, hints deleted: 21.5% → 32.3%. Showed the prompt, not the coordinates, was the failure.

**<span style="color:#B8860B">14 · Region size, live: 80% vs 95%.</span>** Tighter won — 83.5% vs 80.0%, crops answered 100% vs 97.7% correct. Removed distractors, not context.

**<span style="color:#B8860B">15 · Token breakdown.</span>** Crop 17,371 (23% of baseline, every document pays it); fallback pages 46,547 (the 65% that missed). Fallback rate is the only remaining lever.

_(All tables also appear in `my-notes.md` with the surrounding discussion.)_
