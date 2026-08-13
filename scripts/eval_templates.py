"""Learn templates from `build`, then read documents with them and score.

Reported separately for known layouts and unseen ones. The second number is the honest
one — what happens when a vendor we have never met sends an invoice.
"""
from __future__ import annotations

import json, re, sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from api import data, template                                    # noqa: E402
from api.fingerprint import signature, LayoutIndex                # noqa: E402

THRESHOLD = json.loads(Path("data/fingerprint_threshold.json").read_text())["threshold"]


def normalise(s):
    """Compare on content, not formatting.

    Ground truth is normalised (`1290.00`); pages are not (`£1,290.00`). And nearly half
    of all target values are multi-line, so whitespace has to collapse or we would
    under-report our own accuracy by roughly half.
    """
    if s is None:
        return ""
    s = re.sub(r"\s+", " ", str(s)).strip().upper()
    s = s.replace(",", "").replace("£", "").replace("$", "").replace("€", "")
    return s.strip(" .:-")


def main():
    splits = data.splits()
    build = [d for d in splits["build"] if data.has_ocr(d)]
    print(f"learning from {len(build)} documents...", flush=True)

    # Learn from ground-truth layout groups. At build time we know which vendor each
    # document came from — a customer labelling their own invoices knows this too, and
    # doing it any other way lets one bad merge poison a template.
    #
    # Greedy fingerprint grouping was tried first and chains: A matches B, B matches C,
    # so A and C land together even though they are different vendors. It collapsed 722
    # real layouts into 521 and templates learned from mixed vendors read nothing.
    #
    # Fingerprinting still does the runtime job below: given a new document, which of
    # these templates is it?
    groups = defaultdict(list)
    for doc_id in build:
        meta = json.loads(Path(f"data/docile/annotations/{doc_id}.json").read_text())["metadata"]
        groups[str(meta["cluster_id"])].append(doc_id)
    print(f"  {len(groups)} layouts in build")

    index = LayoutIndex(threshold=THRESHOLD)
    for layout_id, docs in groups.items():
        sig = signature(data.words(docs[0]))
        if sig:
            index.add(layout_id, sig)

    templates = {}
    for layout_id, docs in groups.items():
        examples = [(data.fields(d), data.words(d)) for d in docs]
        t = template.learn(examples, layout_id)
        if t.rules:
            templates[layout_id] = t

    rule_count = sum(len(t.rules) for t in templates.values())
    print(f"\nlayouts: {len(index)}   templates with rules: {len(templates)}"
          f"   total rules: {rule_count}")
    print(f"mean rules per template: {rule_count/max(len(templates),1):.1f}\n")

    for split_name in ("dev_seen", "dev_unseen"):
        docs = [d for d in splits[split_name] if data.has_ocr(d)]
        per_field = defaultdict(lambda: [0, 0])       # field -> [correct, total]
        matched = 0

        for doc_id in docs:
            truth = data.fields(doc_id)
            sig = signature(data.words(doc_id))
            m = index.match(sig) if sig else None

            if not (m and m.known and m.layout_id in templates):
                for name in truth:
                    per_field[name][1] += 1
                continue

            matched += 1
            got = template.apply(templates[m.layout_id], data.words(doc_id))
            for name, info in truth.items():
                per_field[name][1] += 1
                if name in got and normalise(got[name]["value"]) == normalise(info["value"]):
                    per_field[name][0] += 1

        total_c = sum(v[0] for v in per_field.values())
        total_n = sum(v[1] for v in per_field.values())
        print(f"=== {split_name}  ({len(docs)} docs) ===")
        print(f"layout matched to a template : {matched}/{len(docs)} ({matched/max(len(docs),1):.0%})")
        print(f"field accuracy               : {total_c}/{total_n} ({total_c/max(total_n,1):.1%})\n")

        rows = sorted(per_field.items(), key=lambda kv: -kv[1][1])[:10]
        print(f"  {'field':<28}{'n':>6}{'acc':>8}")
        for name, (c, n) in rows:
            print(f"  {name:<28}{n:>6}{c/max(n,1):>8.1%}")
        print()

    Path("data/templates.json").write_text(
        json.dumps({k: v.to_dict() for k, v in templates.items()}, indent=1))
    print(f"wrote data/templates.json ({len(templates)} templates)")


if __name__ == "__main__":
    main()
