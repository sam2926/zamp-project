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

**<span style="color:#B8860B">2 · DocILE won on four things.</span>**

- **What it gave us:** 5,680 labelled real documents:
  DocILE's train and val, of which 3,850 are tax invoices and the rest orders, POs and receipts, drawn from public-inspection filings and the UCSF litigation archive.
- **It is actually invoices.** This is a finance operations domain.
- **The schema is relational.** 55 field types, and 93% of documents carry line items (one carries 110), so a query layer has real structure to work with.
- **Bounding boxes ship with it.** Every value's position on the page is labelled, so "click a value, see exactly where it came from on the scan" is reliable to build, not guesswork.
- **It is verifiably hard.** I sampled 400 PDFs: **34% contain no text layer at all.** 2,645 documents come from the UCSF litigation archive, degraded material I could not have faked credibly.
- **Accepted in exchange:** it ships a single OCR engine, so I generate the disagreement signal myself, which the deployed product needed regardless, since a stranger's upload was never in a precomputed file. And access is a gated research licence.

**<span style="color:#B8860B">3 · Kleister-Charity was the strongest contender, and I measured it before rejecting it.</span>**

- It ships **three independent OCR engines per document**, so I could test a hypothesis before committing: on 1,729 documents **no engine wins**, and the union of all three beats every one of them on every field.
- **That result shaped what I built.** The pipeline reads every page several ways instead of picking an engine — a measurement on the dataset I rejected determined the design of the one I chose.
- Rejected as the spine: 8 flat fields, no bounding boxes, and charity reports sit one domain hop from finance operations.

### <span style="color:#1565C0">What did I scope in?</span>

**<span style="color:#B8860B">1 · I narrowed to one document type: tax invoices.</span>**

- 3,512 to build on, 338 to score. Dropped orders, POs, receipts, proformas, credit notes, utility bills, debit notes.
- **Sharper rules.** Line items summing to the total holds on an invoice, not a utility bill. Mixing types would have forced me to weaken the rule for everything.
- **Sharper product.** "Invoice processing" is bought. "Document processing" is researched.
- Most discarded types were unmeasurable anyway, 6 debit notes, 12 utility bills.
- **Kept for free:** 107 orders and 21 receipts held aside as an out-of-distribution test. Real AP inboxes get non-invoices; now I can say what happens when one arrives.

**<span style="color:#B8860B">2 · I chose layout variety over structural uniformity, deliberately.</span>**

- 3,850 invoices span **916 layouts. 519 appear exactly once.** A handful of vendors invoice constantly; a long tail invoiced once.
- **A uniform dataset would have let me build something that already exists and already fails.** Configure-per-layout OCR works until a new vendor appears, then needs a human to reconfigure it. That is the problem, not the solution.
- So nothing in my pipeline assumes where a field sits. It reads each page several ways, checks the arithmetic, and flags disagreement, none of which cares about layout.
- The distribution then splits the work honestly: 6% of layouts carry half the volume and reward caching; the 519 one-offs must work from scratch, every time.
- **I report accuracy separately for repeat and unseen layouts** — the honest number most systems never publish. A 2-point gap, not a cliff, because the region never depended on the layout in the first place. On `val`, `amount_due`, from the saved run:

| layout         | pipeline  | whole-page baseline |
| -------------- | --------- | ------------------- |
| repeat (n=205) | **78.0%** | 74.6%               |
| unseen (n=86)  | **75.6%** | 70.9%               |
| all (n=291)    | 77.3%     | 73.5%               |

## <span style="color:#2E7D32">Architecture</span>

### <span style="color:#1565C0">How much of the page does the model need to see?</span>

**<span style="color:#B8860B">1 · The model reads a small learned region, not the whole page.</span>**

- Every document gets one model call; the decision is how much of the page that call carries.
- Crop to the region the field usually occupies and send only that, about half the tokens for the same answer: `amount_due` scores 77.3% at 86% of the whole-page baseline's tokens, better _and_ cheaper.
- The learning lives in _what the model is shown_: a human correction re-shapes the region, so the crop tightens over time with no per-layout configuration to maintain.

**<span style="color:#B8860B">2 · The only page we never re-read is one we have already read, byte for byte.</span>**

- A SHA-256 of the file short-circuits literal re-uploads — month-end reruns, double-clicks — at no cost.
- A fresh scan is different bytes, so it is still read in full. The cache dedups work; it never skips it.

### <span style="color:#1565C0">Why go deep on one field instead of shallow on many?</span>

**<span style="color:#B8860B">1 · I took one field all the way, rather than many part-way.</span>**

- One field with measured accuracy on held-out data, a real confidence signal and a real cost number is worth more than five fields demoed but never proven.
- It proves the whole pipeline end to end on something unambiguous, instead of spreading thin across many.

### <span style="color:#1565C0">Where on the page do we look for the value?</span>

**<span style="color:#B8860B">1 · I store the neighbourhood, not the pixel.</span>**

- Over a 50×50 grid across thousands of documents, count which cells each field's box lands in, and take the smallest rectangle holding a target share of that mass.
- The same value lands in a consistent region across hundreds of different layouts, even as its exact spot shifts from one scan to the next.
- **Count every cell the box touches, not the cell under its centre**, a centre-based region clips the value's own text out of the crop.
- **A solid rectangle, not the ragged set of hottest cells**, a ragged set has holes a value can fall through, while a rectangle contains anything within its bounds.

**<span style="color:#B8860B">2 · The region is not an extractor.</span>**

- It never reads the value. It only decides what the model is allowed to see, which is why it holds up where a fixed box would miss.

### <span style="color:#1565C0">How tight is the crop, and what goes inside it?</span>

**<span style="color:#B8860B">1 · Tighter beat wider, against my prediction.</span>**

- I expected the wider rectangle to keep more captions and win. The 80% region beat the 95% one: `amount_due` 83.5% vs 80.0%, at 82% vs 98% of baseline tokens.
- **Tightening removed distractors, not context:** the wide rectangle swept in line-item amounts and subtotals, many money-shaped tokens to choose between, while the tight one sits on the totals block.

**<span style="color:#B8860B">2 · Flat text beat every coordinate format.</span>**

- Same field, same page, only the payload changed:

| format sent to the model        | accuracy  | tokens |
| ------------------------------- | --------- | ------ |
| flat text (reading-order lines) | **35.5%** | 24,431 |
| JSON `[word, x, y]`             | 26.9%     | 77,248 |
| words only, no line breaks      | 10.8%     | 32,156 |

- **Let go: coordinates.** They tripled the cost and lost accuracy. Line breaks alone are worth 25 points, delete them and a two-column invoice interleaves into nonsense.
- Why flat text works: words are grouped into lines using each word's own height as the ruler (`|Δy| < 0.7 × height`). Bare coordinates give the model no ruler, and it merges lines that sit only fractionally apart into one.

**<span style="color:#B8860B">3 · A correction to my own conclusion.</span>**

- I first blamed coordinates for the model's errors. Removing my _layout hints_ from the same JSON took it 21.5% → 32.3%, the prompt was the variable, not the coordinates. The hint ("words close together form a block") is exactly what glued addresses onto company names.

### <span style="color:#1565C0">What happens when the value isn't in the crop?</span>

**<span style="color:#B8860B">1 · Fall back to the whole page, not the unsearched remainder.</span>**

- Sending only the complement is cheaper and was tempting. It breaks on a value straddling the boundary: half in the crop, half in the remainder, and neither call sees a whole answer.
- So a miss costs crop + full page. That is the price of never returning a truncated value.
- The fallback rate is now the main cost lever, every point off it is real tokens saved (see the Future Optimizations tab).

### <span style="color:#1565C0">When do we trust the answer, and when does a human see it?</span>

**<span style="color:#B8860B">1 · The model is never trusted on its own word.</span>**

- The returned value must appear verbatim in the OCR text, anything else was invented. Then deterministic format checks: length, contains letters, not a caption ("BILL TO"), not identical to the vendor name.

**<span style="color:#B8860B">2 · The strongest confidence signal is free and measured.</span>**

- **Did the value land in its expected region?** When the crop answered, 102/103 were correct (99%); when it fell back, 123/188 (65%). One measured signal separates the two.
- **Let go, for now: the hand-set weights.** `0.55 × ocr + 0.45 × heat` flags almost every document for review, correct ones included, noise. It stays retired until it is fit on labelled data rather than guessed.

### <span style="color:#1565C0">How did I measure without fooling myself?</span>

**<span style="color:#B8860B">1 · A dev slice carved from train, so val is sat once.</span>**

- Measuring on the data I built from tells me nothing. Checking against `val` each time quietly spends it, every look is a small fit, and ten cycles in the headline is inflated.
- So 400 train documents become `dev`, a practice exam I can retake freely; `val` is the real exam, touched once.

**<span style="color:#B8860B">2 · The dev slice is cut two ways, because there are two questions.</span>**

- **Random documents held out** — does it work on a new invoice from a vendor we know?
- **Whole layouts held out** — does it work on a vendor we have never seen? The honest number, and the one most systems never publish.

### <span style="color:#1565C0">How and where does it ship?</span>

**<span style="color:#B8860B">1 · One container, on Hugging Face Spaces.</span>**

- docTR pulls in torch — the image is ~2.5GB and needs real RAM, which rules out Vercel, Netlify and Render's free tier. HF Spaces gives 16GB free with a public URL.
- FastAPI serves the React build from the same origin: no CORS, no second deploy pipeline, no two services pointing at each other. They redeploy together, fine at this size, wrong at scale.

**<span style="color:#B8860B">2 · No API key ships with the repo.</span>**

- Anyone running it supplies their own. Everything except the model call runs locally. OCR, region cropping, validation, scoring, so a committed key would only bill the author for every stranger's usage.
