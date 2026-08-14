# <span style="color:#D6336C">Decisions</span>

## <span style="color:#2E7D32">Problem statement selection</span>

### <span style="color:#1565C0">Why did I pick "turn messy documents into structured data" over the other two?</span>

**<span style="color:#B8860B">1 · I chose the problem I could measure objectively.</span>**

- With document extraction, every field has a correct value that already sits on the page. That means I can measure how often the system gets it right and report it as a plain number, which let me base every decision in the project on evidence rather than impression.
- Extraction offered the firmer ground on which to justify the results.

**<span style="color:#B8860B">2 · What I chose not to pursue, and why.</span>**

- The other two problems are open-ended by their nature: success is multi-dimensional and partly a matter of interpretation, so validating a solution to the same rigorous standard would call for a much larger evaluation, one not feasible within a five-day project.
- "Learning a task by watching" is the most exciting, but it is also the hardest to evaluate in a short project.
- Even so, a version of that idea does live inside what I built: the system learns each customer's documents from the examples they have already labelled, and improves as people correct its mistakes. It is one part of the pipeline rather than its foundation, and on its own it would need considerably more training and testing before I would rely on it.

**<span style="color:#B8860B">3 · It contains a hard sub-problem worth solving properly.</span>**

- Invoices come in a very large number of layouts, many of which a system will never have seen before, so any approach that has to be configured for each new supplier fails the moment a new one arrives.
- Many documents also have no machine-readable text, or are poor-quality scans, so a field's exact position on the page can never be taken for granted.
- The improvement I set out to make is this: most existing services extract data by sending the entire document to a large language model. I wanted to do better on both cost and accuracy by using the fact that invoices of a similar kind tend to place the same information in roughly the same area, the total amount, for example, usually appears towards the bottom-right of the page.

## <span style="color:#2E7D32">Data</span>

### <span style="color:#1565C0">Why did I choose the data that I chose?</span>

**<span style="color:#B8860B">1 · I ruled out synthetic data before comparing anything.</span>**

- With generated data I would be playing both sides, inventing the documents and then testing myself against them, so I could never uncover a failure I had not already thought to build in.
- And because the correct answers are fixed at the moment the data is created, every accuracy score would really just be marking its own work.

**<span style="color:#B8860B">2 · DocILE was the best fit, for several reasons.</span>**

- **What it provides.** 5,680 labelled real documents from DocILE's training and validation sets. Of these, 3,850 are tax invoices and the rest are orders, purchase orders and receipts, drawn from public-inspection filings and the UCSF litigation archive.
- **They are genuine invoices,** which is the domain finance operations actually works in.
- **The data is richly structured.** It defines 55 different field types, and 93% of the documents contain line items (one has as many as 110), so there is real structure for a query layer to work with.
- **It records where every value sits.** Each field is labelled with its position on the page, which makes a feature like "click a value and see exactly where it came from on the scan" straightforward to build rather than a matter of guesswork.
- **It is genuinely difficult.** In a sample of 400 PDFs, 34% had no readable text layer at all, and 2,645 of the documents come from the UCSF litigation archive, degraded, real-world material that would have been hard to fake convincingly.

**<span style="color:#B8860B">3 · Kleister-Charity was the strongest alternative, and I measured it before setting it aside.</span>**

- It comes with three independent OCR readings of every document, which let me test an idea before committing to any dataset: across 1,729 documents, no single OCR engine was consistently best, and combining all three beat every individual one on every field.
- That finding shaped how I think about reading a page, treating a single OCR reading with some caution rather than trusting it outright. The shipped pipeline still reads with one engine, and I have left reading with several as a clear next step.
- I did not use it as the main dataset because it has only eight simple fields, records nothing about where values sit on the page, and charity reports are a step removed from the finance-operations setting I was aiming at.

**<span style="color:#B8860B">4 · It is a real problem that a community is actively working on.</span>**

- It is a problem people genuinely need solved: finance teams still enter these documents by hand today, so the work addresses a real need rather than a demonstration.
- Extracting data from documents is something research groups and companies work on continually, publishing results and pushing accuracy higher year after year.
- That gives me an external standard to measure against .

### <span style="color:#1565C0">What did I scope in?</span>

**<span style="color:#B8860B">1 · I narrowed the work to a single document type: tax invoices (depth over breadth)</span>**

- This left 3,512 documents to build with and 338 to measure against, after setting aside orders, purchase orders, receipts, proformas, credit notes, utility bills and debit notes.
- Keeping to one type lets the checking rules be strict and specific. On an invoice, for instance, the line items should add up to the total, a rule that would not hold if I mixed in other kinds of document.
- It also makes the product clearer: a business buys "invoice processing" as a concrete service, whereas "document processing" is a much vaguer proposition.

**<span style="color:#B8860B">2 · I deliberately chose variety of layout over uniformity.</span>**

- The 3,850 invoices span 916 distinct layouts, and 519 of those appear only once. A few suppliers invoice constantly, while a long tail of suppliers show up just a single time.
- A neat, uniform dataset would have let me build something that already exists and already fails in practice: a system configured for each specific layout, which works until a new supplier appears and then needs a person to set it up again. That is the problem, not the solution.
- Because of this, my approach never assumes where a field will be. It learns the general area a value tends to occupy rather than a fixed spot, so a new layout does not break it.
- The variety also splits the work honestly: the top 6% of layouts account for half of all the invoices and are worth caching, while the 519 one-off layouts have to be handled from scratch every time.
- Finally, I report accuracy separately for layouts the system has seen before and layouts it has not. The second figure is the honest one, and the one most systems never publish. On the validation set, for the "amount due" field I focused the demo on, the two are close rather than far apart, which matters, because the method was never tied to a particular layout in the first place:

| layout              | my pipeline |
| ------------------- | ----------- |
| seen before (n=205) | **78.0%**   |
| never seen (n=86)   | **75.6%**   |
| all (n=291)         | 77.3%       |

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
