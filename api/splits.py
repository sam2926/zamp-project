"""Data splits.

train is the textbook, dev is a practice exam we can retake freely, val is the real exam
sat once. Everything intermediate is measured on dev so val stays untouched until the end.

dev is cut two ways because there are two different questions:

  dev_seen    random documents whose layout also appears in build
              → does a template work on a new invoice from a vendor we know?

  dev_unseen  every document of ~120 layouts held out entirely
              → does anything work on a vendor we have never seen?

The second is the honest number. A random split alone would hide it, because every held-out
document would still have had its layout learned from its siblings.
"""
from __future__ import annotations

import json
import random
from collections import defaultdict
from pathlib import Path

DATA = Path("data/docile")
SEED = 17
DEV_UNSEEN_LAYOUTS = 120
DEV_SEEN_DOCS = 250


def _invoices(split: str) -> list[tuple[str, int]]:
    out = []
    for doc_id in json.loads((DATA / f"{split}.json").read_text()):
        meta = json.loads((DATA / "annotations" / f"{doc_id}.json").read_text()).get("metadata") or {}
        if meta.get("document_type") == "tax_invoice":
            out.append((doc_id, meta.get("cluster_id")))
    return out


def build_splits() -> dict[str, list[str]]:
    """Deterministic. Same seed always yields the same split."""
    rng = random.Random(SEED)
    docs = _invoices("train")

    by_layout = defaultdict(list)
    for doc_id, layout in docs:
        by_layout[layout].append(doc_id)

    # Hold out whole layouts — prefer small ones so we lose little training signal.
    layouts = sorted(by_layout, key=lambda c: (len(by_layout[c]), str(c)))
    unseen_layouts = set(layouts[:DEV_UNSEEN_LAYOUTS])
    dev_unseen = [d for c in unseen_layouts for d in by_layout[c]]

    remaining = [d for d, c in docs if c not in unseen_layouts]
    rng.shuffle(remaining)
    dev_seen = remaining[:DEV_SEEN_DOCS]
    build = remaining[DEV_SEEN_DOCS:]

    return {
        "build": build,
        "dev_seen": dev_seen,
        "dev_unseen": dev_unseen,
        "val": [d for d, _ in _invoices("val")],
    }


def load_splits(path: Path = Path("data/splits.json")) -> dict[str, list[str]]:
    if path.exists():
        return json.loads(path.read_text())
    splits = build_splits()
    path.write_text(json.dumps(splits, indent=1))
    return splits


if __name__ == "__main__":
    s = build_splits()
    Path("data/splits.json").write_text(json.dumps(s, indent=1))
    layouts = {k: len({json.loads((DATA / "annotations" / f"{d}.json").read_text())["metadata"]["cluster_id"]
                       for d in v}) for k, v in s.items()}
    print(f"{'split':<12}{'docs':>7}{'layouts':>10}   purpose")
    print("-" * 62)
    for name, purpose in [
        ("build", "learn templates from this"),
        ("dev_seen", "known layout, new document"),
        ("dev_unseen", "layout never seen before"),
        ("val", "final number, touched once"),
    ]:
        print(f"{name:<12}{len(s[name]):>7}{layouts[name]:>10}   {purpose}")
    overlap = set(s["build"]) & (set(s["dev_seen"]) | set(s["dev_unseen"]))
    print(f"\nleakage check — build ∩ dev: {len(overlap)} documents")
