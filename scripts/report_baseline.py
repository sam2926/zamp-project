"""Summarise a saved run. Reads JSONL, makes no model calls."""
import json, sys
from pathlib import Path
from collections import Counter

path = Path(sys.argv[1] if len(sys.argv) > 1 else "data/runs/baseline_full_page.jsonl")
rows = [json.loads(l) for l in path.read_text().splitlines() if l.strip()]
n = len(rows)
print(f"{path}   {n} documents\n")

print(f"{'criterion':<14}{'matched':>9}{'rate':>8}   what it means")
print("-" * 78)
for key, meaning in [
    ("exact",     "identical after stripping punctuation"),
    ("line_set",  "same lines, any order — the fair one for multi-line values"),
    ("any_line",  "got at least one complete line of the answer"),
    ("substring", "one contains the other"),
]:
    c = sum(r["verdicts"].get(key, False) for r in rows)
    print(f"{key:<14}{c:>9}{c/max(n,1):>8.1%}   {meaning}")

err = sum(1 for r in rows if r.get("error"))
tok = sum(r["tokens_sent"] for r in rows)
sec = sum(r["seconds"] for r in rows)
print(f"\n{'errors':<14}{err:>9}")
print(f"{'tokens':<14}{tok:>9}   {tok/max(n,1):.0f} per document")
print(f"{'time':<14}{sec:>9.0f}s  {sec/max(n,1):.2f}s per document")
print(f"{'cost':<14}{'':>9}   ${tok/1e6*0.15:.4f} at gpt-4o-mini input pricing")

miss = [r for r in rows if not r["verdicts"].get("line_set")]
if miss:
    print(f"\n{len(miss)} not matched on line_set — first 12:\n")
    print(f"{'said':<38}{'expected':<38}")
    print("-" * 78)
    for r in miss[:12]:
        print(f"{(r['said'] or 'ERROR')[:36]:<38}{r['expected'].replace(chr(10),' / ')[:36]:<38}")
