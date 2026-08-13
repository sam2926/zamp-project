"""Tune the layout-match threshold on train, then report it once on val.

DocILE ships `cluster_id` — its own grouping of which documents share a layout. That is
ground truth for this task, so we can measure the fingerprint directly instead of guessing.

The question asked of every pair of documents: do we agree with DocILE about whether these
two share a layout? Scored as pair-level precision and recall, because the grouping matters,
not the arbitrary id attached to it.
"""
from __future__ import annotations

import json, random, sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from api.fingerprint import signature, jaccard          # noqa: E402

DATA = Path("data/docile")
CACHE = Path("data/ocr_cache")
MAX_PAIRS = 400_000


def load(split: str, limit: int | None = None) -> list[tuple[str, int, frozenset]]:
    """(doc_id, cluster_id, signature) for tax invoices we have OCR for."""
    out = []
    for doc_id in json.loads((DATA / f"{split}.json").read_text()):
        meta = json.loads((DATA / "annotations" / f"{doc_id}.json").read_text()).get("metadata") or {}
        if meta.get("document_type") != "tax_invoice" or meta.get("cluster_id") is None:
            continue

        cached = CACHE / f"{doc_id}.json"
        if cached.exists():                                    # our own docTR run
            doc = json.loads(cached.read_text())
            words = [
                {"text": w["text"], "box": w["box"], "page": p["page_idx"]}
                for p in doc["pages"] for w in p["words"]
            ]
        else:                                                  # fall back to shipped OCR
            ocr = json.loads((DATA / "ocr" / f"{doc_id}.json").read_text())
            words = [
                {"text": w["value"],
                 "box": [w["geometry"][0][0], w["geometry"][0][1],
                         w["geometry"][1][0], w["geometry"][1][1]],
                 "page": p["page_idx"]}
                for p in ocr["pages"] for b in p["blocks"] for l in b["lines"] for w in l["words"]
            ]

        sig = signature(words)
        if sig:
            out.append((doc_id, meta["cluster_id"], sig))
        if limit and len(out) >= limit:
            break
    return out


def sample_pairs(docs, cap=MAX_PAIRS):
    """All same-cluster pairs, plus a matched sample of different-cluster pairs.

    Same-layout pairs are rare — the vast majority of random pairs are different
    layouts, so scoring on all pairs would drown the signal.
    """
    random.seed(3)
    by_cluster = defaultdict(list)
    for i, (_, cluster, _) in enumerate(docs):
        by_cluster[cluster].append(i)

    same = [(a, b) for idxs in by_cluster.values()
            for n, a in enumerate(idxs) for b in idxs[n + 1:]]

    diff, seen = [], set()
    target = min(len(same) * 5, cap)
    while len(diff) < target:
        a, b = random.randrange(len(docs)), random.randrange(len(docs))
        if a == b or docs[a][1] == docs[b][1] or (a, b) in seen:
            continue
        seen.add((a, b))
        diff.append((a, b))
    return same, diff


def evaluate(docs, same, diff, threshold):
    tp = sum(1 for a, b in same if jaccard(docs[a][2], docs[b][2]) >= threshold)
    fp = sum(1 for a, b in diff if jaccard(docs[a][2], docs[b][2]) >= threshold)
    fn = len(same) - tp
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return precision, recall, f1


def main():
    print("loading train...", flush=True)
    train = load("train")
    print(f"  {len(train)} invoices, {len({c for _, c, _ in train})} layouts, "
          f"mean signature {sum(len(s) for _, _, s in train)/len(train):.0f} words\n")

    same, diff = sample_pairs(train)
    print(f"pairs: {len(same)} same-layout, {len(diff)} different-layout\n")

    print(f"{'threshold':>10}{'precision':>11}{'recall':>9}{'F1':>8}")
    print("-" * 38)
    best = (0.0, 0.0)
    for t in [0.01, 0.02, 0.03, 0.04, 0.05, 0.06, 0.08, 0.10, 0.15, 0.20, 0.30, 0.50]:
        p, r, f1 = evaluate(train, same, diff, t)
        flag = ""
        if f1 > best[1]:
            best, flag = (t, f1), "  <-"
        print(f"{t:>10.2f}{p:>11.1%}{r:>9.1%}{f1:>8.3f}{flag}")

    threshold = best[0]
    print(f"\nchosen threshold (train): {threshold}")

    print("\nloading val (never used for tuning)...", flush=True)
    val = load("val")
    vsame, vdiff = sample_pairs(val)
    p, r, f1 = evaluate(val, vsame, vdiff, threshold)
    print(f"  {len(val)} invoices, {len({c for _, c, _ in val})} layouts")
    print(f"  {len(vsame)} same-layout pairs, {len(vdiff)} different-layout pairs")
    print(f"\nVAL  precision {p:.1%}  recall {r:.1%}  F1 {f1:.3f}")

    Path("data/fingerprint_threshold.json").write_text(
        json.dumps({"threshold": threshold,
                    "train_f1": round(best[1], 4),
                    "val": {"precision": round(p, 4), "recall": round(r, 4), "f1": round(f1, 4)}},
                   indent=1))
    print("\nwrote data/fingerprint_threshold.json")


if __name__ == "__main__":
    main()
