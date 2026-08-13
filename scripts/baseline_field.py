"""Whole-page flat-text baseline for any field. Same method as the billing-name run.

Usage: baseline_field.py FIELD [N]
"""
import json, os, re, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from api import data
from api.extract import as_text
from api.model import get_asker

PROMPTS = {
    "customer_billing_name": """You read text extracted from a scanned invoice and return one field.

The field is the CUSTOMER BILLING NAME: the organisation or person being billed — who owes
the money. It is not the vendor, not the sender, not whoever issued the invoice.

Rules:
- Return the value exactly as it appears in the text. Do not tidy, expand or reformat it.
- Return only the name itself, never its caption.
- If it is not present, return exactly: NOT_FOUND

Reply with the value alone. No explanation, no quotes, no label.""",

    "amount_due": """You read text extracted from a scanned invoice and return one field.

The field is the AMOUNT DUE: the total the customer must actually pay on this invoice. If
part has already been paid, it is the remaining balance, not the gross total. Captions
include "Amount Due", "Balance Due", "Total Due", "Please Pay This Amount", "Net Due".

Rules:
- Return the value exactly as it appears, including any currency symbol and separators.
  If the text reads "$1,024.00", return "$1,024.00" — do not convert to 1024.
- Return only the amount, never its caption.
- If it is not present, return exactly: NOT_FOUND

Reply with the value alone. No explanation, no quotes, no label.""",
}

def squash(s): return re.sub(r"[^A-Z0-9]", "", (s or "").upper())

def verdicts(said, expected):
    s = squash(said); lines = [squash(l) for l in expected.split("\n") if squash(l)]
    # numeric equality, so "$1,024.00" and "1024.00" are the same amount
    def num(x):
        m = re.findall(r"[\d.,]+", x or "")
        if not m: return None
        try: return round(float(max(m, key=len).replace(",", "")), 2)
        except ValueError: return None
    return {"exact": s == squash(expected),
            "line_set": sorted({squash(l) for l in (said or "").split("\n") if squash(l)}) == sorted(set(lines)),
            "any_line": any(l and l in s for l in lines),
            "substring": bool(s) and (s in squash(expected) or squash(expected) in s),
            "numeric": num(said) is not None and num(said) == num(expected)}

def main():
    field = sys.argv[1] if len(sys.argv) > 1 else "amount_due"
    limit = int(sys.argv[2]) if len(sys.argv) > 2 else 10_000
    system = PROMPTS[field]
    OUT = Path(f"data/runs/baseline_{field}.jsonl")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    done = ({json.loads(l)["doc_id"] for l in OUT.read_text().splitlines() if l.strip()}
            if OUT.exists() else set())
    todo = [d for d in data.splits()["val"][:limit]
            if data.has_ocr(d) and d not in done
            and (f := data.fields(d).get(field)) and f.get("page", 0) == 0]

    ask, live = get_asker()
    provider = "openai/" + os.environ.get("EXTRACTION_MODEL", "gpt-4o-mini")
    est = sum(len(as_text([w for w in data.words(d) if w.get("page", 0) == 0])) // 4 for d in todo)
    print(f"field     : {field}")
    print(f"model     : {'LIVE ' + provider if live else 'OFFLINE stub'}")
    print(f"documents : {len(todo)} to run, {len(done)} already done")
    print(f"tokens    : ~{est:,}   cost ≈ ${est/1e6*0.15:.4f}")
    if live and todo and input("\nproceed? [y/N] ").strip().lower() != "y":
        print("cancelled"); return
    print()

    t0 = time.time()
    with OUT.open("a") as fh:
        for n, doc_id in enumerate(todo, 1):
            words = [w for w in data.words(doc_id) if w.get("page", 0) == 0]
            text = as_text(words); expected = data.fields(doc_id)[field]["value"]
            try:
                said, error = ask(system, text).strip(), None
            except Exception as exc:
                said, error = None, repr(exc)[:200]
            v = verdicts(said, expected) if said else {}
            fh.write(json.dumps({"doc_id": doc_id, "field": field, "expected": expected,
                                 "said": said, "error": error, "verdicts": v,
                                 "tokens_sent": len(text)//4, "model": provider}) + "\n")
            fh.flush()
            print(f"{'OK ' if v.get('exact') or v.get('numeric') else '   '}{n:>3}/{len(todo)}  "
                  f"{(said or 'ERROR')[:24]:<26} exp {expected[:24]}", flush=True)
    print(f"\ndone in {time.time()-t0:.0f}s → {OUT}")

if __name__ == "__main__":
    main()
