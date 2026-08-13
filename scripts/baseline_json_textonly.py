"""Baseline variant: OCR words as a JSON array of strings, no coordinates.

Same 93 documents, whole page. This is flat text minus the line breaks — the words in
reading order, but with no indication of which share a line. Run to check whether that
line structure was carrying anything.
"""
import json, os, re, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from api import data
from api.model import get_asker

BASELINE = Path("data/runs/baseline_full_page.jsonl")
OUT = Path("data/runs/baseline_json_textonly.jsonl")

SYSTEM = """You read OCR output from a scanned invoice and return one field.

The input is a JSON array of strings. Each entry is one word, in reading order — left to
right, top to bottom down the page.

The field is the CUSTOMER BILLING NAME: the organisation or person being billed — who owes
the money. Not the vendor, not the sender, not whoever issued the invoice.

Rules:
- Return the value exactly as the words read. Do not tidy, expand or reformat.
- Return only the name, never its caption. If you see "BILL TO" then "ACME CORP", the
  answer is "ACME CORP".
- Join consecutive words with spaces.
- If the billing name is not present, return exactly: NOT_FOUND

Reply with the value alone. No explanation, no quotes, no JSON."""

def squash(s): return re.sub(r"[^A-Z0-9]", "", (s or "").upper())

def verdicts(said, expected):
    s = squash(said); lines = [squash(l) for l in expected.split("\n") if squash(l)]
    return {"exact": s == squash(expected),
            "line_set": sorted({squash(l) for l in (said or "").split("\n") if squash(l)}) == sorted(set(lines)),
            "any_line": any(l and l in s for l in lines),
            "substring": bool(s) and (s in squash(expected) or squash(expected) in s)}

def payload(words):
    """Just the words. No positions, no keys — the array order is the reading order."""
    return json.dumps([w["text"] for w in words], separators=(",", ":"))

def main():
    OUT.parent.mkdir(parents=True, exist_ok=True)
    base = {json.loads(l)["doc_id"]: json.loads(l)
            for l in BASELINE.read_text().splitlines() if l.strip()}
    done = ({json.loads(l)["doc_id"] for l in OUT.read_text().splitlines() if l.strip()}
            if OUT.exists() else set())
    todo = [d for d in base if d not in done]

    ask, live = get_asker()
    provider = "openai/" + os.environ.get("EXTRACTION_MODEL", "gpt-4o-mini")
    est = sum(len(payload([w for w in data.words(d) if w.get("page", 0) == 0])) // 4 for d in todo)
    txt = sum(base[d]["tokens_sent"] for d in todo)
    print(f"model     : {'LIVE ' + provider if live else 'OFFLINE stub'}")
    print(f"documents : {len(todo)}")
    print(f"tokens    : ~{est:,}  vs flat text {txt:,}  = {est/max(txt,1):.1f}x")
    print(f"cost      : ≈ ${est/1e6*0.15:.4f}")
    if live and todo and input("\nproceed? [y/N] ").strip().lower() != "y":
        print("cancelled"); return
    print()

    t0 = time.time()
    with OUT.open("a") as fh:
        for n, doc_id in enumerate(todo, 1):
            words = [w for w in data.words(doc_id) if w.get("page", 0) == 0]
            body = payload(words); expected = base[doc_id]["expected"]
            try:
                said, error = ask(SYSTEM, body).strip(), None
            except Exception as exc:
                said, error = None, repr(exc)[:200]
            v = verdicts(said, expected) if said else {}
            fh.write(json.dumps({
                "doc_id": doc_id, "expected": expected, "said": said, "error": error,
                "verdicts": v, "tokens_sent": len(body) // 4,
                "text_tokens": base[doc_id]["tokens_sent"],
                "baseline_said": base[doc_id]["said"],
                "baseline_line_set": base[doc_id]["verdicts"].get("line_set", False),
                "model": provider}) + "\n"); fh.flush()
            print(f"{'OK ' if v.get('line_set') else '   '}{n:>3}/{len(todo)}  "
                  f"{(said or 'ERROR')[:34]:<36} exp {expected.replace(chr(10),' / ')[:26]}", flush=True)
    print(f"\ndone in {time.time()-t0:.0f}s → {OUT}")

if __name__ == "__main__":
    main()
