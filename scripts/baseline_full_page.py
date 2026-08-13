"""Baseline: hand the model the whole page and ask for the billing name.

No crop, no region, no fallback — the naive approach, so everything else has a number to
beat. Two things it establishes: how often a model gets this right at all, and what a full
page actually costs in tokens.

Every document's inputs, output and verdict are written to JSONL as the run proceeds, so a
paid run is never lost and can be re-analysed without paying again. Resumable: documents
already in the file are skipped.
"""
from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from api import data                                              # noqa: E402
from api.extract import SYSTEM, as_text                           # noqa: E402
from api.model import get_asker                                   # noqa: E402

FIELD = "customer_billing_name"
OUT = Path("data/runs/baseline_full_page.jsonl")


def squash(s: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", (s or "").upper())


def verdicts(said: str | None, expected: str) -> dict:
    """Several ways of being right, because 'correct' is genuinely ambiguous here.

    Ground-truth values are often multi-line — `PHILIP MORRIS\\nPHILIP MORRIS` — and the
    annotator's line order does not always match reading order. Scoring only on an exact
    concatenated match penalises answers that are obviously correct, so record every
    criterion and decide which to report once we can see them side by side.
    """
    s, e = squash(said), squash(expected)
    lines = [squash(l) for l in expected.split("\n") if squash(l)]
    return {
        "exact": s == e,
        # same lines, any order — handles the annotator writing them the other way round
        "line_set": sorted({squash(l) for l in (said or "").split("\n") if squash(l)}) ==
                    sorted(set(lines)),
        # got at least one full line of the answer, e.g. the company without the attn line
        "any_line": any(l and l in s for l in lines),
        # the answer contains what we said, or vice versa
        "substring": bool(s) and (s in e or e in s),
    }


def main():
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else 10
    OUT.parent.mkdir(parents=True, exist_ok=True)

    done = set()
    if OUT.exists():
        done = {json.loads(l)["doc_id"] for l in OUT.read_text().splitlines() if l.strip()}

    val = data.splits()["val"][:limit]
    todo = [d for d in val
            if data.has_ocr(d) and d not in done
            and (f := data.fields(d).get(FIELD)) and f.get("page", 0) == 0]

    ask, live = get_asker()
    import os
    provider = ("openai/" + os.environ.get("EXTRACTION_MODEL", "gpt-4o-mini")
                if os.environ.get("OPENAI_API_KEY")
                else "anthropic/" + os.environ.get("EXTRACTION_MODEL", "claude-haiku-4-5-20251001"))

    est_tokens = sum(len(as_text([w for w in data.words(d) if w.get("page", 0) == 0])) // 4
                     for d in todo)
    print(f"model      : {'LIVE ' + provider if live else 'OFFLINE stub'}")
    print(f"documents  : {len(todo)} to run, {len(done)} already done and skipped")
    print(f"tokens in  : ~{est_tokens:,}   cost ≈ ${est_tokens / 1e6 * 0.15:.3f}")
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
            text = as_text(words)
            expected = data.fields(doc_id)[FIELD]["value"]

            t0 = time.time()
            try:
                said = ask(SYSTEM, text).strip()
                error = None
            except Exception as exc:                      # keep going, record the failure
                said, error = None, repr(exc)[:200]

            row = {
                "doc_id": doc_id,
                "expected": expected,
                "said": said,
                "error": error,
                "verdicts": verdicts(said, expected) if said else {},
                "tokens_sent": len(text) // 4,
                "words_on_page": len(words),
                "seconds": round(time.time() - t0, 2),
                "model": provider,
                "at": time.time(),
            }
            fh.write(json.dumps(row) + "\n")
            fh.flush()                                    # never lose a paid result

            mark = "OK " if row["verdicts"].get("line_set") else "   "
            print(f"{mark}{n:>3}/{len(todo)}  {(said or 'ERROR')[:34]:<36} "
                  f"exp {expected.replace(chr(10), ' / ')[:30]}", flush=True)

    print(f"\ndone in {time.time() - started:.0f}s → {OUT}")
    print("run scripts/report_baseline.py to summarise")


if __name__ == "__main__":
    main()
