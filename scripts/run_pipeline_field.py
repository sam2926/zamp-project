"""Region-crop pipeline for any field, compared against its saved flat-text baseline.

Fallback answers are reused from the baseline run rather than paying twice, but their
tokens are charged in full — in production there would be no saved result to reuse.
"""
import json, os, re, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from api import data
from api.extract import as_text, locate, validate, score
from api.model import get_asker
from api.region import load as load_region, crop
from scripts.baseline_field import PROMPTS, verdicts

def main():
    field = sys.argv[1] if len(sys.argv) > 1 else "amount_due"
    suffix = sys.argv[2] if len(sys.argv) > 2 else ""      # e.g. "_80" for the 80% region
    BASE = Path(f"data/runs/baseline_{field}.jsonl")
    OUT  = Path(f"data/runs/pipeline_{field}{suffix}.jsonl")
    region = load_region(Path(f"data/region_{field}{suffix}.json"))
    system = PROMPTS[field]
    base = {json.loads(l)["doc_id"]: json.loads(l) for l in BASE.read_text().splitlines() if l.strip()}
    done = ({json.loads(l)["doc_id"] for l in OUT.read_text().splitlines() if l.strip()}
            if OUT.exists() else set())
    todo = [d for d in base if d not in done]

    ask, live = get_asker()
    provider = "openai/" + os.environ.get("EXTRACTION_MODEL", "gpt-4o-mini")
    est = sum(len(as_text(crop([w for w in data.words(d) if w.get("page",0)==0], region)))//4 for d in todo)
    print(f"field     : {field}")
    print(f"region    : {region.area:.1%} of the page")
    print(f"documents : {len(todo)}")
    print(f"tokens    : ~{est:,} for the crop calls   cost ≈ ${est/1e6*0.15:.4f}")
    if live and todo and input("\nproceed? [y/N] ").strip().lower() != "y":
        print("cancelled"); return
    print()

    t0=time.time()
    with OUT.open("a") as fh:
        for n, doc_id in enumerate(todo, 1):
            words=[w for w in data.words(doc_id) if w.get("page",0)==0]
            expected=base[doc_id]["expected"]
            cropped=crop(words, region); ctext=as_text(cropped)
            ctok=len(ctext)//4; ptok=base[doc_id]["tokens_sent"]
            try:
                csaid = ask(system, ctext).strip() if ctext.strip() else "NOT_FOUND"
                error=None
            except Exception as exc:
                csaid, error = "NOT_FOUND", repr(exc)[:200]
            fb = csaid in ("NOT_FOUND","")
            said = base[doc_id]["said"] if fb else csaid
            tokens = ctok+ptok if fb else ctok
            box, oconf = locate(said, words) if said else (None,0.0)
            heat = region.heat(box) if box else 0.0
            checks = validate(said, words)
            conf = score(oconf, heat, fb, checks)
            v = verdicts(said, expected) if said else {}
            fh.write(json.dumps({"doc_id":doc_id,"field":field,"expected":expected,
                "crop_said":csaid,"fell_back":fb,"said":said,"error":error,"verdicts":v,
                "confidence":conf,"ocr_confidence":round(oconf,3),"position_heat":round(heat,3),
                "failed_checks":[c["rule"] for c in checks if not c["passed"]],
                "crop_tokens":ctok,"page_tokens":ptok,"tokens_charged":tokens,
                "baseline_said":base[doc_id]["said"],
                "baseline_ok":base[doc_id]["verdicts"].get("numeric") or base[doc_id]["verdicts"].get("exact"),
                "model":provider})+"\n"); fh.flush()
            ok = v.get("numeric") or v.get("exact")
            print(f"{'OK ' if ok else '   '}{'FB ' if fb else '   '}{n:>3}/{len(todo)}  "
                  f"{(said or 'NONE')[:22]:<24} exp {expected[:18]:<20} {tokens:>4}tok", flush=True)
    print(f"\ndone in {time.time()-t0:.0f}s → {OUT}")

if __name__ == "__main__":
    main()
