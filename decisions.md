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

### <span style="color:#1565C0">How much of the page does the model need to read?</span>

**<span style="color:#B8860B">1 · The model reads only a small, learned area of each page, not the whole thing.</span>**

- When a document goes to a language model, the decision is how much of the page that single call has to carry.
- Instead of the entire page, I send only the area where the field of interest appears. On the "amount due" field, that is both more accurate and less costly than reading the whole page. (How that area is worked out is the next question below.)
- **More accurate** — the region crop returns the correct value more often than the whole page does:

| whole page | region crop | gain  |
| ---------- | ----------- | ----- |
| 73.5%      | **77.3%**   | +3.8% |

- **Fewer tokens** — and it does so while sending less text to the model:

| whole page | region crop | saved |
| ---------- | ----------- | ----- |
| 74,181     | **63,918**  | 14%   |

- The system learns that area from the data rather than being told it. When a person corrects an answer, the area is nudged to fit, so it tightens over time and needs no manual setup for each new layout.

**<span style="color:#B8860B">2 · The one document it never has to read twice is an exact duplicate.</span>**

- Before doing anything else, the system takes a fingerprint of the file's exact bytes (a SHA-256 hash). If that fingerprint has been seen before, the same file re-uploaded, a month-end rerun, a double-click, it returns the stored answer at no cost.
- A fresh scan of the same invoice is a different file, so it is still read in full. This skips only genuine duplicates, never real work.

### <span style="color:#1565C0">Why focus on one field rather than many?</span>

**<span style="color:#B8860B">1 · I took a single field the whole way, instead of many part of the way.</span>**

- One field, measured properly on held-out data with a real accuracy figure and a real cost figure, tells you far more than five fields shown in a demo but never verified.
- It also let me prove the entire pipeline end to end on something unambiguous, rather than spreading the effort thinly and leaving every part half-finished.

### <span style="color:#1565C0">How does the system decide where on the page to look?</span>

**<span style="color:#B8860B">1 · It learns the general neighbourhood a value sits in, not an exact position.</span>**

- Working across thousands of documents, I divide each page into a grid of 50×50 cells and count how often the target value falls in each cell. The result is a heat-map of where that value tends to appear.
- From that heat-map I take the smallest rectangle that still captures most of those appearances. The same value reliably lands inside this rectangle across hundreds of different layouts, even though its exact spot shifts a little from one scan to the next.
- I count every cell the value's box touches, not just the cell under its centre. Using the centre alone would draw the rectangle too tightly and clip part of the value out of the crop.
- I also use one solid rectangle rather than a scattered set of the hottest cells. A scattered set leaves gaps a value can fall into, whereas a rectangle contains anything within its edges.

**<span style="color:#B8860B">2 · This area only decides what the model sees; it does not read the value itself.</span>**

- The rectangle never extracts anything. Its only job is to narrow down what the model is shown. Because it describes a general area rather than a fixed point, it keeps working even where a rigid, fixed position would miss.

### <span style="color:#1565C0">How large should the crop be, and in what form is it sent?</span>

**<span style="color:#B8860B">1 · Sending the text as plain laid-out lines beat sending it with coordinates.</span>**

- I compared several ways of passing the same page text to the model, changing only the format:

| how the text was sent to the model               | accuracy  | tokens |
| ------------------------------------------------ | --------- | ------ |
| plain text, kept in reading-order lines          | **35.5%** | 24,431 |
| a list of words with their x, y coordinates      | 26.9%     | 77,248 |
| the same words, but with the line breaks removed | 10.8%     | 32,156 |

- Attaching coordinates roughly tripled the token cost and made accuracy worse, so I dropped them. The line breaks alone are worth about 25 points: remove them and a two-column invoice collapses into interleaved nonsense.
- Plain lines work because the words are grouped into lines using each word's own height as the yardstick for what counts as the same line. Given only raw coordinates, the model has no such yardstick and merges lines that sit only slightly apart.

**<span style="color:#B8860B">3 · One conclusion of mine turned out to be wrong, and it is worth recording.</span>**

- At first I blamed the coordinates for the poorer results. But when I removed the layout hints from my own prompt and left the coordinates in, accuracy rose from 21.5% to 32.3%. The prompt was the real problem, not the coordinates: my hint ("words close together form a block") is exactly what led the model to glue street addresses onto company names.

### <span style="color:#1565C0">What happens when the value is not inside the crop?</span>

**<span style="color:#B8860B">1 · The system falls back to the whole page, not to the leftover part of it.</span>**

- Sending only the remaining, un-cropped part of the page would be cheaper, and it was tempting. But a value that straddles the crop's edge would be split, half inside the crop, half in the remainder and neither call would see it whole.
- So a miss costs the crop plus a full-page read. That is the price of never returning half of a value.
- This makes the miss rate the main thing left to improve on cost, since every fallback avoided is real tokens saved. (This is picked up on the Future Optimizations page.)

### <span style="color:#1565C0">When is an answer trusted, and when does a person check it?</span>

**<span style="color:#B8860B">1 · The model's word is never taken on its own.</span>**

- Any value it returns has to appear, character for character, in the text the OCR actually read; anything else is treated as invented.
- After that come a few simple format checks — a sensible length, containing letters, not just a caption such as "BILL TO", and not identical to the vendor's own name.

**<span style="color:#B8860B">2 · The most reliable confidence signal costs nothing and is measured, not guessed.</span>**

- The single best predictor of a correct answer is simply whether the value came from the crop or from the whole-page fallback. When the crop answered, 102 of 103 were right (99%); when the system fell back to the full page, only 123 of 188 were (65%).
- I deliberately do not rely on the hand-picked scoring weights I first wrote (`0.55 × OCR confidence + 0.45 × position`). In practice they flag almost every document for review, correct ones included, which is no signal at all. They stay switched off until they can be fitted properly on labelled data rather than guessed.

### <span style="color:#1565C0">How did I measure results without misleading myself?</span>

**<span style="color:#B8860B">1 · I kept one slice of data as a final exam, sat only once.</span>**

- Measuring on the same data I built the system from proves nothing. But repeatedly checking against the official test set quietly uses it up: each look nudges a choice to fit it, and after enough rounds the headline figure flatters rather than informs.
- So I set aside 400 documents from the training data to act as a practice set I could reuse freely, and kept the real test set for a single, final measurement. Every number above comes from data held back in this way.

**<span style="color:#B8860B">2 · I split that practice set two ways, because there are two different questions.</span>**

- Holding out random documents answers one question: does it work on a new invoice from a supplier we have already seen?
- Holding out whole layouts answers the harder one: does it work on a supplier we have never seen before? That second figure is the honest one, and the one many systems never report.

### <span style="color:#1565C0">How and where is it deployed?</span>

**<span style="color:#B8860B">1 · A single container on Google Cloud Run.</span>**

- The OCR library (docTR) depends on PyTorch, which makes the container about 2.5GB and needs real memory to run. That rules out the small serverless free tiers such as Vercel, Netlify and Render. Google Cloud Run runs the container directly, scales to zero when idle so it costs nothing between visits, and serves it at a stable public URL.
- The same server hosts both the API and the built front-end from one place, so there is no cross-origin configuration and no second deployment to keep in step. The trade-off is that the two are released together — fine at this scale, though it would not suit a much larger system.

**<span style="color:#B8860B">2 · No API key is shipped with the code.</span>**

- Anyone running it supplies their own key. Everything except the model call — the OCR, the cropping, the checks and the scoring — runs locally, so a key committed to the repository would do nothing but bill me for every stranger's usage.
