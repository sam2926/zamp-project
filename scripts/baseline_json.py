"""Baseline variant: send the OCR as JSON with coordinates, not flattened text.

Same 93 documents, same whole-page scope. The only change is what the model receives:
every word as an object with its text and its box, so layout and position survive.
`conf` is dropped — it is our signal, not something the model should reason about.
"""
import json, os, re, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from api import data
from api.model import get_asker

FIELD = "customer_billing_name"
BASELINE = Path("data/runs/baseline_full_page.jsonl")
OUT = Path("data/runs/baseline_json.jsonl")

SYSTEM = """You read OCR output from a scanned invoice and return one field.

The input is a JSON array. Each entry is one word:

  ["WORD", x, y]

where x and y are the top-left corner of that word as 0-1 fractions of the page, with
0,0 at the top-left of the page. So x is how far across, y is how far down.

Use the coordinates. Words with a similar y are on the same line. Words close in both x
and y form a block. A caption like "BILL TO" sits above or to the left of the value it
labels, so look just below and to the right of one.

The field is the CUSTOMER BILLING NAME: the organisation or person being billed — who owes
the money. Not the vendor, not the sender, not whoever issued the invoice.

Rules:
- Return the value exactly as the words read. Do not tidy, expand or reformat.
- Return only the name, never its caption.
- Join words on the same line with spaces; separate lines with a newline.
- If the billing name is not present, return exactly: NOT_FOUND

Reply with the value alone. No explanation, no quotes, no JSON."""

def squash(s): return re.sub(r"[^A-Z0-9]", "", (s or "").upper())

def verdicts(said, expected):
    s, e = squash(said), squash(expected)
    lines = [squash(l) for l in expected.split("\n") if squash(l)]
    return {"exact": s == e,
            "line_set": sorted({squash(l) for l in (said or "").split("\n") if squash(l)}) == sorted(set(lines)),
            "any_line": any(l and l in s for l in lines),
            "substring": bool(s) and (s in e or e in s)}

def payload(words):
    """Words as positional arrays: ["WORD", x, y].

    Measured against the alternatives on these 93 documents:
      flat text          24,431 tokens   no position at all
      {"t","b"} 4 floats 168,093         6.9x
      [word, x, y]        77,248         3.2x   <- this

    Most of the cost was the four floats per word, not the key names — shortening
    "text"/"box" to "t"/"b" bought only 10%. Dropping right/bottom is what pays: to know
    two words share a line, or that a caption sits above a value, the top-left corner is
    enough, and a word's width is roughly implied by the word itself. Two decimals because
    a scan is not accurate to three.
    """
    return json.dumps([[w["text"], round(w["box"][0], 2), round(w["box"][1], 2)]
                       for w in words], separators=(",", ":"))

def main():
    OUT.parent.mkdir(parents=True, exist_ok=True)
    base = {json.loads(l)["doc_id"]: json.loads(l)
            for l in BASELINE.read_text().splitlines() if l.strip()}
    done = set()
    if OUT.exists():
        done = {json.loads(l)["doc_id"] for l in OUT.read_text().splitlines() if l.strip()}
    todo = [d for d in base if d not in done]

    ask, live = get_asker()
    provider = "openai/" + os.environ.get("EXTRACTION_MODEL", "gpt-4o-mini")
    est = sum(len(payload([w for w in data.words(d) if w.get("page", 0) == 0])) // 4 for d in todo)
    text_tok = sum(base[d]["tokens_sent"] for d in todo)
    print(f"model      : {'LIVE ' + provider if live else 'OFFLINE stub'}")
    print(f"documents  : {len(todo)}")
    print(f"tokens in  : ~{est:,} as JSON  vs {text_tok:,} as text  = {est/max(text_tok,1):.1f}x")
    print(f"cost       : ≈ ${est/1e6*0.15:.4f}")
    print(f"output     : {OUT}")
    if live and todo:
        if input("\nproceed? [y/N] ").strip().lower() != "y":
            print("cancelled"); return
    print()

    t0 = time.time()
    with OUT.open("a") as fh:
        for n, doc_id in enumerate(todo, 1):
            words = [w for w in data.words(doc_id) if w.get("page", 0) == 0]
            body = payload(words)
            expected = base[doc_id]["expected"]
            s0 = time.time()
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
                "seconds": round(time.time() - s0, 2), "model": provider,
            }) + "\n"); fh.flush()
            mark = "OK " if v.get("line_set") else "   "
            print(f"{mark}{n:>3}/{len(todo)}  {(said or 'ERROR')[:34]:<36} "
                  f"exp {expected.replace(chr(10),' / ')[:28]}", flush=True)
    print(f"\ndone in {time.time()-t0:.0f}s → {OUT}")

if __name__ == "__main__":
    main()
