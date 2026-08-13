"""Read a PDF the moment it arrives — no cache, no ground truth, just the bytes.

A stranger's upload was never in anyone's precomputed OCR file, so the deployed product has
to run its own reader. This is the one heavy dependency: docTR pulls in torch, the model is
a couple of hundred MB, and the first call after a cold start loads it (tens of seconds).
So the model is a lazily-built singleton, warmed at startup in the background, and the import
lives inside the function — the app process can boot without paying for torch up front.

Output matches `api/data.words()` exactly — [{"text", "box": [l,t,r,b], "page", "conf"}]
with normalised coordinates — so everything downstream (crop, fingerprint, extract) is blind
to whether the words came from here or from the cache.
"""
from __future__ import annotations

import threading

_model = None
_lock = threading.Lock()


def _predictor():
    """The docTR OCR model, built once and shared. Guarded so two uploads racing to be
    first do not each build their own copy."""
    global _model
    if _model is None:
        with _lock:
            if _model is None:
                from doctr.models import ocr_predictor
                _model = ocr_predictor(pretrained=True)
    return _model


def warm() -> None:
    """Build the model ahead of the first upload. Safe to call from a background thread;
    failures are swallowed so a warmup problem never takes the whole app down with it."""
    try:
        _predictor()
    except Exception:
        pass


def ready() -> bool:
    return _model is not None


def read(pdf_bytes: bytes) -> tuple[list[dict], int]:
    """PDF bytes → (words, page_count). Raises on an unreadable PDF; the caller turns that
    into an `unreadable` outcome for that one document rather than failing the batch."""
    from doctr.io import DocumentFile

    doc = DocumentFile.from_pdf(pdf_bytes)
    pages = _predictor()(doc).export()["pages"]

    words: list[dict] = []
    for p in pages:
        page_idx = p["page_idx"]
        for block in p["blocks"]:
            for line in block["lines"]:
                for w in line["words"]:
                    (x0, y0), (x1, y1) = w["geometry"]
                    words.append({
                        "text": w["value"],
                        "box": [round(x0, 5), round(y0, 5), round(x1, 5), round(y1, 5)],
                        "page": page_idx,
                        "conf": round(w["confidence"], 4),
                    })
    return words, len(pages)
