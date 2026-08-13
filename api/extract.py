"""Pull the customer billing name out of an invoice.

Crop the page to the region this field usually occupies, ask the model to read that slice,
and fall back to the whole page only when the crop comes back empty. Then check the answer
deterministically and score how much to trust it.

The model is never trusted on its own word: it must return a span that literally appears in
the OCR text, and everything after it is arithmetic and lookups.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass, asdict

from .region import Region, crop, rows
from .store import connect, file_hash, get_cached, put_cached

FIELD = "customer_billing_name"
MODEL = os.environ.get("EXTRACTION_MODEL", "claude-haiku-4-5-20251001")

# Bump whenever a change would make the same document produce a different answer — the
# crop, the prompt, the checks, the scoring. The dedup cache is keyed on file bytes, so
# without this a redeploy keeps serving answers the current code would never produce, and
# an evaluation silently reports the previous pipeline's numbers as if they were new.
PIPELINE = "2-overlap-crop"

SYSTEM = """You read text extracted from a scanned invoice and return one field.

The field is the CUSTOMER BILLING NAME: the organisation or person being billed — who owes
the money. It is not the vendor, not the sender, not whoever issued the invoice.

Rules:
- Return the value exactly as it appears in the text. Do not tidy, expand or reformat it.
- Return only the name itself, never its caption. If the text reads "BILL TO: ACME CORP",
  the answer is "ACME CORP".
- The text comes from OCR of a scan and may be imperfect. Copy what is there.
- If the billing name is not present, return exactly: NOT_FOUND

Reply with the value alone. No explanation, no quotes, no label."""

# Captions that sit next to the value and get returned instead of it.
LABELS = {
    "BILL TO", "BILLED TO", "BILL TO:", "SOLD TO", "SHIP TO", "REMIT TO", "INVOICE",
    "CUSTOMER", "CLIENT", "ACCOUNT", "TO", "ATTN", "ATTENTION", "NAME", "ADDRESS",
    "STATEMENT", "PAYER", "ADVERTISER", "AGENCY",
}


@dataclass
class Extraction:
    value: str | None
    confidence: float
    status: str                       # ok · review · not_found
    box: list[float] | None
    page: int
    used_fallback: bool
    ocr_confidence: float
    position_heat: float
    checks: list[dict]
    tokens_sent: int
    reason: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)


def as_text(words: list[dict]) -> str:
    """Words as reading-order lines. The model sees text with layout, not a bag of tokens."""
    return "\n".join(" ".join(w["text"] for w in row) for row in rows(words))


def locate(value: str, words: list[dict]) -> tuple[list[float] | None, float]:
    """Find the returned value back in the OCR words: its box, and the OCR's own confidence.

    This is also the hallucination check. A model given text must return a span *from* that
    text — anything we cannot find, it invented.
    """
    target = _squash(value)
    if not target:
        return None, 0.0
    for size in range(min(len(words), 12), 0, -1):
        for i in range(len(words) - size + 1):
            run = words[i:i + size]
            if _squash(" ".join(w["text"] for w in run)) == target:
                confs = [w.get("conf", 1.0) for w in run]
                return ([min(w["box"][0] for w in run), min(w["box"][1] for w in run),
                         max(w["box"][2] for w in run), max(w["box"][3] for w in run)],
                        sum(confs) / len(confs))
    return None, 0.0


def _squash(s: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", (s or "").upper())


def validate(value: str | None, words: list[dict], vendor: str | None = None) -> list[dict]:
    """Deterministic checks. None of these consult a model."""
    checks: list[dict] = []

    def add(rule: str, passed: bool, detail: str = ""):
        checks.append({"rule": rule, "passed": passed, "detail": detail})

    if not value:
        add("present", False, "no value returned")
        return checks

    v = value.strip()
    add("present", True)
    add("in_source_text", _squash(v) in _squash(" ".join(w["text"] for w in words)),
        "the value must appear in the OCR text; anything else was invented")
    add("length", 2 <= len(v) <= 80, f"{len(v)} characters")
    add("has_letters", bool(re.search(r"[A-Za-z]", v)), "a name contains letters")
    add("not_only_punctuation", bool(re.sub(r"[^A-Za-z0-9]", "", v)))
    add("not_a_caption", v.strip(" :").upper() not in LABELS,
        "returned the caption instead of the value")
    add("word_count", 1 <= len(v.split()) <= 8, f"{len(v.split())} words")
    if vendor:
        add("not_the_vendor", _squash(v) != _squash(vendor),
            "the payer is not the sender")
    return checks


def score(ocr_conf: float, heat: float, used_fallback: bool, checks: list[dict]) -> float:
    """Two independent signals, plus a hard veto from the checks.

    Neither signal is the model's opinion of itself: one is the OCR engine's own certainty
    about those characters, the other is how typical the position is across thousands of
    labelled invoices.

    Weights are placeholders until fitted on labelled data — see scripts/fit_confidence.py.
    """
    if any(not c["passed"] for c in checks if c["rule"] in
           ("present", "in_source_text", "not_a_caption")):
        return 0.0
    base = 0.55 * ocr_conf + 0.45 * heat
    if used_fallback:
        base *= 0.8            # found outside its usual region: unusual, so less certain
    soft = [c for c in checks if not c["passed"]]
    return round(max(0.0, min(base - 0.1 * len(soft), 1.0)), 3)


def extract_file(raw: bytes, filename: str, words: list[dict], region: Region, ask,
                 vendor: str | None = None, threshold: float = 0.75,
                 conn=None, tag: str = "") -> tuple[dict, bool]:
    """Step 1 then the rest. Returns (result, was_cached).

    The hash check comes before anything expensive: no OCR, no model call, no cost. It only
    catches literal re-uploads, which is exactly what month-end reruns and double clicks are.

    `tag` separates results that came from different askers. Without it an offline stub run
    poisons the cache for the paid run that follows: same file, same pipeline, so the live
    call is skipped and the stub's answer is returned as if it were real.
    """
    conn = conn or connect()
    sha = file_hash(raw)
    version = PIPELINE + tag

    cached = get_cached(conn, sha)
    if cached is not None and cached.get("pipeline") == version:
        return cached, True

    result = extract(words, region, ask, vendor, threshold).to_dict()
    result["sha256"] = sha
    result["pipeline"] = version
    put_cached(conn, sha, filename, result)
    return result, False


def extract(words: list[dict], region: Region, ask, vendor: str | None = None,
            threshold: float = 0.75) -> Extraction:
    """`ask(system, text) -> str` is the model call, injected so this is testable offline."""
    cropped = crop(words, region)
    text = as_text(cropped)
    used_fallback = False

    value = ask(SYSTEM, text).strip() if text.strip() else "NOT_FOUND"

    if value == "NOT_FOUND" or not value:
        # The 8%: the name sat outside its usual region. Send the whole page, not the
        # remainder — a value straddling the boundary would be split across both calls.
        used_fallback = True
        text = as_text([w for w in words if w.get("page", 0) == 0])
        value = ask(SYSTEM, text).strip()

    tokens = len(text) // 4

    if value == "NOT_FOUND" or not value:
        return Extraction(None, 0.0, "not_found", None, 0, used_fallback, 0.0, 0.0,
                          validate(None, words), tokens,
                          "no billing name found on this page")

    box, ocr_conf = locate(value, words)
    heat = region.heat(box) if box else 0.0
    checks = validate(value, words, vendor)
    conf = score(ocr_conf, heat, used_fallback, checks)
    failed = [c for c in checks if not c["passed"]]

    return Extraction(
        value=value,
        confidence=conf,
        status="ok" if conf >= threshold and not failed else "review",
        box=box,
        page=0,
        used_fallback=used_fallback,
        ocr_confidence=round(ocr_conf, 3),
        position_heat=round(heat, 3),
        checks=checks,
        tokens_sent=tokens,
        reason=failed[0]["detail"] or failed[0]["rule"] if failed else None,
    )
