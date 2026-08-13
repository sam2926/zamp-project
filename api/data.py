"""Loading documents: OCR words and annotated fields, in one shape.

Prefers our own docTR cache and falls back to the OCR shipped with DocILE. Both are docTR,
so the shapes match; only word segmentation differs slightly.
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

DATA = Path("data/docile")
CACHE = Path("data/ocr_cache")


def words(doc_id: str) -> list[dict]:
    """[{"text", "box": [l,t,r,b], "page", "conf"}] — normalised coordinates."""
    cached = CACHE / f"{doc_id}.json"
    if cached.exists():
        doc = json.loads(cached.read_text())
        return [
            {"text": w["text"], "box": w["box"], "page": p["page_idx"], "conf": w["conf"]}
            for p in doc["pages"] for w in p["words"]
        ]

    ocr = json.loads((DATA / "ocr" / f"{doc_id}.json").read_text())
    return [
        {"text": w["value"],
         "box": [w["geometry"][0][0], w["geometry"][0][1],
                 w["geometry"][1][0], w["geometry"][1][1]],
         "page": p["page_idx"],
         "conf": w.get("confidence", 1.0)}
        for p in ocr["pages"] for b in p["blocks"] for l in b["lines"] for w in l["words"]
    ]


def fields(doc_id: str) -> dict[str, dict]:
    """Document-level ground truth: {name: {"value", "box", "page"}}.

    Where a field appears more than once, the first occurrence wins — DocILE annotates
    every instance, but a template needs one place to look.
    """
    ann = json.loads((DATA / "annotations" / f"{doc_id}.json").read_text())
    out = {}
    for f in ann.get("field_extractions", []):
        if f["fieldtype"] in out:
            continue
        out[f["fieldtype"]] = {"value": f.get("text"), "box": f["bbox"], "page": f["page"]}
    return out


def line_items(doc_id: str) -> list[dict]:
    """[{"id": int, "fields": {name: {...}}}] grouped by line_item_id."""
    ann = json.loads((DATA / "annotations" / f"{doc_id}.json").read_text())
    rows: dict[int, dict] = {}
    for f in ann.get("line_item_extractions", []):
        row = rows.setdefault(f["line_item_id"], {})
        name = f["fieldtype"].replace("line_item_", "")
        if name not in row:
            row[name] = {"value": f.get("text"), "box": f["bbox"], "page": f["page"]}
    return [{"id": k, "fields": v} for k, v in sorted(rows.items())]


@lru_cache(maxsize=1)
def splits() -> dict[str, list[str]]:
    from .splits import load_splits
    return load_splits()


def has_ocr(doc_id: str) -> bool:
    return (CACHE / f"{doc_id}.json").exists() or (DATA / "ocr" / f"{doc_id}.json").exists()
