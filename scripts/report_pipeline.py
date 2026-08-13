"""Compare the pipeline run against the baseline. Reads JSONL, no model calls."""
import json, sys
from pathlib import Path

P = Path("data/runs/pipeline_region.jsonl")
rows = [json.loads(l) for l in P.read_text().splitlines() if l.strip()]
n = len(rows)
base_tok = sum(r["page_tokens"] for r in rows)
pipe_tok = sum(r["tokens_charged"] for r in rows)

print(f"{n} documents — whole page (baseline) vs region crop (pipeline)\n")
print(f"{'criterion':<14}{'baseline':>10}{'pipeline':>10}{'change':>9}")
print("-" * 43)
for k in ("exact", "line_set", "any_line", "substring"):
    b = sum(r["baseline_line_set"] if k == "line_set" else 0 for r in rows) if k == "line_set" else None
    bb = sum(1 for r in rows if r.get("baseline_line_set")) if k == "line_set" else None
    p = sum(r["verdicts"].get(k, False) for r in rows)
    if k == "line_set":
        print(f"{k:<14}{bb/n:>9.1%}{p/n:>10.1%}{(p-bb)/n:>+9.1%}")
    else:
        print(f"{k:<14}{'—':>10}{p/n:>10.1%}{'':>9}")

fb = [r for r in rows if r["fell_back"]]
print(f"\n{'fell back':<24}{len(fb)}/{n} = {len(fb)/n:.1%}")
if fb:
    print(f"{'  of those, correct':<24}{sum(r['verdicts']['line_set'] for r in fb)}/{len(fb)}")
nofb = [r for r in rows if not r["fell_back"]]
print(f"{'crop answered':<24}{len(nofb)}/{n} = {len(nofb)/n:.1%}")
if nofb:
    print(f"{'  of those, correct':<24}{sum(r['verdicts']['line_set'] for r in nofb)}/{len(nofb)}"
          f" = {sum(r['verdicts']['line_set'] for r in nofb)/len(nofb):.1%}")

print(f"\n{'tokens: whole page':<24}{base_tok:>8,}")
print(f"{'tokens: pipeline':<24}{pipe_tok:>8,}   {pipe_tok/base_tok:.0%} of baseline")
print(f"{'saved':<24}{base_tok-pipe_tok:>8,}   {1-pipe_tok/base_tok:.0%}")

ok = [r for r in rows if r["status"] == "ok"]
print(f"\n{'auto-accepted':<24}{len(ok)}/{n} = {len(ok)/n:.1%}")
if ok:
    print(f"{'  of those, correct':<24}{sum(r['verdicts']['line_set'] for r in ok)}/{len(ok)}"
          f" = {sum(r['verdicts']['line_set'] for r in ok)/len(ok):.1%}")
rev = [r for r in rows if r["status"] == "review"]
if rev:
    print(f"{'flagged for review':<24}{len(rev)}/{n} = {len(rev)/n:.1%}")
    print(f"{'  of those, correct':<24}{sum(r['verdicts']['line_set'] for r in rev)}/{len(rev)}"
          f" = {sum(r['verdicts']['line_set'] for r in rev)/len(rev):.1%}")

print(f"\n{'-'*112}\nPER DOCUMENT\n{'-'*112}")
print(f"{'#':<4}{'expected':<30}{'crop said':<28}{'FB':<4}{'final':<28}{'ok?':<5}{'conf':>5}{'tok':>6}")
print("-" * 112)
for i, r in enumerate(rows, 1):
    print(f"{i:<4}{r['expected'].replace(chr(10),' / ')[:28]:<30}"
          f"{(r['crop_said'] or '')[:26]:<28}{'Y' if r['fell_back'] else '':<4}"
          f"{(r['said'] or 'NONE')[:26]:<28}"
          f"{('yes' if r['verdicts']['line_set'] else 'no'):<5}{r['confidence']:>5.2f}{r['tokens_charged']:>6}")
