"""Run the real pipeline over the same documents as the baseline, and compare.

Crop to the learned region, ask the model, and on an empty crop fall back to the whole
page. The fallback answer is taken from the saved baseline run rather than paying for the
identical call twice — but its tokens are counted in full, because in production nobody
would have that result sitting in a file.

Every document's inputs, both model answers, all signals and all verdicts go to JSONL as
the run proceeds.
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from api import data                                              # noqa: E402
from api.extract import SYSTEM, as_text, locate, validate, score  # noqa: E402
from api.model import get_asker                                   # noqa: E402
from api.region import load as load_region, crop                  # noqa: E402

FIELD = "customer_billing_name"
BASELINE = Path("data/runs/baseline_full_page.jsonl")
OUT = Path("data/runs/pipeline_region.jsonl")
THRESHOLD = 0.75


def squash(s: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", (s or "").upper())


def verdicts(said: str | None, expected: str) -> dict:
    s, e = squash(said), squash(expected)
    lines = [squash(l) for l in expected.split("\n") if squash(l)]
    return {
        "exact": s == e,
        "line_set": sorted({squash(l) for l in (said or "").split("\n") if squash(l)}) ==
                    sorted(set(lines)),
        "any_line": any(l and l in s for l in lines),
        "substring": bool(s) and (s in e or e in s),
    }


def main():
    OUT.parent.mkdir(parents=True, exist_ok=True)
    base = {json.loads(l)["doc_id"]: json.loads(l)
            for l in BASELINE.read_text().splitlines() if l.strip()}

    done = set()
    if OUT.exists():
        done = {json.loads(l)["doc_id"] for l in OUT.read_text().splitlines() if l.strip()}

    todo = [d for d in base if d not in done]
    region = load_region(Path("data/region_customer_billing_name.json"))
    ask, live = get_asker()
    provider = ("openai/" + os.environ.get("EXTRACTION_MODEL", "gpt-4o-mini")
                if os.environ.get("OPENAI_API_KEY")
                else "anthropic/" + os.environ.get("EXTRACTION_MODEL", "claude-haiku-4-5-20251001"))

    est = 0
    for d in todo:
        words = [w for w in data.words(d) if w.get("page", 0) == 0]
        est += len(as_text(crop(words, region))) // 4

    print(f"model      : {'LIVE ' + provider if live else 'OFFLINE stub'}")
    print(f"region     : {region.area:.1%} of the page")
    print(f"documents  : {len(todo)} to run, {len(done)} already done")
    print(f"tokens in  : ~{est:,} for the crop calls   cost ≈ ${est / 1e6 * 0.15:.4f}")
    print(f"fallbacks  : answer reused from the baseline run, tokens still counted")
    print(f"output     : {OUT}")
    if live and todo:
        if input("\nproceed? [y/N] ").strip().lower() != "y":
            print("cancelled")
            return
    print()

    started = time.time()
    with OUT.open("a") as fh:
        for n, doc_id in enumerate(todo, 1):
            words = [w for w in data.words(doc_id) if w.get("page", 0) == 0]
            expected = base[doc_id]["expected"]
            cropped = crop(words, region)
            crop_text = as_text(cropped)
            crop_tokens = len(crop_text) // 4
            page_tokens = base[doc_id]["tokens_sent"]

            t0 = time.time()
            try:
                crop_said = ask(SYSTEM, crop_text).strip() if crop_text.strip() else "NOT_FOUND"
                error = None
            except Exception as exc:
                crop_said, error = "NOT_FOUND", repr(exc)[:200]

            fell_back = crop_said in ("NOT_FOUND", "")
            if fell_back:
                # Same call the baseline already made — reuse the answer, pay the tokens.
                said = base[doc_id]["said"]
                tokens = crop_tokens + page_tokens
            else:
                said = crop_said
                tokens = crop_tokens

            box, ocr_conf = locate(said, words) if said else (None, 0.0)
            heat = region.heat(box) if box else 0.0
            checks = validate(said, words,
                              (data.fields(doc_id).get("vendor_name") or {}).get("value"))
            conf = score(ocr_conf, heat, fell_back, checks)
            v = verdicts(said, expected)

            row = {
                "doc_id": doc_id,
                "expected": expected,
                "crop_said": crop_said,
                "fell_back": fell_back,
                "said": said,
                "error": error,
                "verdicts": v,
                "confidence": conf,
                "status": "ok" if conf >= THRESHOLD and all(c["passed"] for c in checks) else "review",
                "ocr_confidence": round(ocr_conf, 3),
                "position_heat": round(heat, 3),
                "failed_checks": [c["rule"] for c in checks if not c["passed"]],
                "crop_tokens": crop_tokens,
                "page_tokens": page_tokens,
                "tokens_charged": tokens,
                "baseline_said": base[doc_id]["said"],
                "baseline_line_set": base[doc_id]["verdicts"].get("line_set", False),
                "seconds": round(time.time() - t0, 2),
                "model": provider,
            }
            fh.write(json.dumps(row) + "\n")
            fh.flush()

            mark = "OK " if v["line_set"] else "   "
            fb = "FB " if fell_back else "   "
            print(f"{mark}{fb}{n:>3}/{len(todo)}  {(said or 'NONE')[:32]:<34} "
                  f"conf {conf:.2f}  {tokens:>4}tok", flush=True)

    print(f"\ndone in {time.time() - started:.0f}s → {OUT}")
    print("run scripts/report_pipeline.py to compare against the baseline")


if __name__ == "__main__":
    main()
