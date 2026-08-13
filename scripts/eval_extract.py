"""Score the extractor. Runs offline without a key, live with one.

Every run — paid or free — is written to data/runs/ as one JSON line per document, and
every result goes through the same SQLite store the API uses. A model call the user paid
for is never allowed to leave nothing behind but a percentage.

    .venv/bin/python scripts/eval_extract.py 10           # 10 documents from val
    .venv/bin/python scripts/eval_extract.py 10 dev_seen  # a split you may look at often
"""
import sys, os, json, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from api import data, extract as ex
from api.region import load
from api.model import get_asker
from api.scoring import matches, squash, contains_value
from api.store import connect

FIELD = "customer_billing_name"
PDFS = Path("data/docile/pdfs")
RUNS = Path("data/runs")


def main():
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else 10
    split = sys.argv[2] if len(sys.argv) > 2 else "val"

    region = load(Path("data/region_customer_billing_name.json"))
    ask, live = get_asker()
    provider = ("openai/" + os.environ.get("EXTRACTION_MODEL", "gpt-4o-mini")
                if os.environ.get("OPENAI_API_KEY") else
                "anthropic/" + os.environ.get("EXTRACTION_MODEL", "claude-haiku-4-5-20251001"))

    print(f"model:    {'LIVE ' + provider if live else 'OFFLINE stub — no API key, accuracy is not real'}")
    print(f"split:    {split}")
    print(f"region:   {region.area:.1%} of the page")
    print(f"pipeline: {ex.PIPELINE}\n")

    docs = [d for d in data.splits()[split] if data.has_ocr(d)][:limit]

    if live:
        # Rule 6: never spend the user's key without showing what it costs first.
        est = len(docs) * 700
        rate = 0.15 if "gpt-4o-mini" in provider else 1.00      # $ per 1M input tokens
        print(f"about to make up to {len(docs)} live calls to {provider}")
        print(f"~{est:,} input tokens, roughly ${est / 1e6 * rate:.4f}")
        if input("proceed? [y/N] ").strip().lower() != "y":
            print("cancelled")
            return
        print()

    RUNS.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    run_path = RUNS / f"{stamp}-{split}-{'live' if live else 'offline'}.jsonl"
    conn = connect()

    ok = strict_ok = tot = fallback = flagged = cached = reachable = 0
    crop_tok = full_tok = 0
    t0 = time.time()

    with run_path.open("w") as log:
        for doc in docs:
            fields = data.fields(doc)
            truth = fields.get(FIELD)
            if not truth or truth.get("page", 0) != 0:
                continue                       # nothing to score against on page 1
            tot += 1

            words = data.words(doc)
            page1 = [w for w in words if w.get("page", 0) == 0]
            full_tok += len(ex.as_text(page1)) // 4

            pdf = PDFS / f"{doc}.pdf"
            raw = pdf.read_bytes() if pdf.exists() else doc.encode()
            result, was_cached = ex.extract_file(
                raw, pdf.name, words, region, ask,
                vendor=(fields.get("vendor_name") or {}).get("value"), conn=conn,
                tag="" if live else "-stub")

            hit = matches(result["value"], truth["value"])
            in_crop = contains_value(truth["value"], ex.crop(words, region))

            ok += hit
            strict_ok += squash(result["value"]) == squash(truth["value"])
            cached += was_cached
            reachable += in_crop
            crop_tok += result["tokens_sent"]
            fallback += result["used_fallback"]
            flagged += result["status"] == "review"

            log.write(json.dumps({
                "doc": doc, "sha256": result.get("sha256"), "cached": was_cached,
                "truth": truth["value"], "predicted": result["value"],
                "hit": hit, "truth_in_crop": in_crop,
                "confidence": result["confidence"], "status": result["status"],
                "used_fallback": result["used_fallback"],
                "tokens_sent": result["tokens_sent"],
                "failed_checks": [c["rule"] for c in result["checks"] if not c["passed"]],
            }) + "\n")

    dt = time.time() - t0
    n = max(tot, 1)
    print(f"{'documents':<26}{tot}   ({cached} served from cache, no model call)")
    print(f"{'exact match':<26}{ok}/{tot} = {ok/n:.1%}")
    print(f"{'  same, order-sensitive':<26}{strict_ok}/{tot} = {strict_ok/n:.1%}   "
          f"← what the old scorer reported")
    print(f"{'truth reachable in crop':<26}{reachable}/{tot} = {reachable/n:.1%}   "
          f"← ceiling for the crop path")
    print(f"{'needed fallback':<26}{fallback}/{tot} = {fallback/n:.1%}")
    print(f"{'flagged for review':<26}{flagged}/{tot} = {flagged/n:.1%}")
    print(f"{'tokens sent':<26}{crop_tok} vs {full_tok} whole-page = {crop_tok/max(full_tok,1):.0%}")
    print(f"{'time':<26}{dt:.1f}s ({dt/n:.2f}s/doc)")
    print(f"\nper-document results: {run_path}")


if __name__ == "__main__":
    main()
