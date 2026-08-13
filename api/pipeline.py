"""Extract one field from one document's words. The field is `amount_due`.

This is the region-crop path from `scripts/run_pipeline_field.py`, moved behind a clean
function so both the batch script and the live server run identical logic: crop the page to
the field's region, ask the model to read that slice, and fall back to the whole page only
when the crop comes back empty. Then check the answer deterministically and score it.

The model is never trusted on its own word — the returned value must appear verbatim in the
OCR text, or it is treated as invented and flagged rather than reported as the answer.
"""
from __future__ import annotations

from .extract import as_text, locate
from .fields import CONF_CROP, CONF_FALLBACK, validate_amount
from .region import Region, crop


def _row(value, status, confidence, box, reason, used_fallback, checks, tokens):
    return {
        "value": value,
        "status": status,                 # ok · review · not_found
        "confidence": round(confidence, 2),
        "page": 0,
        "box": box,
        "reason": reason,
        "used_fallback": used_fallback,
        "checks": checks,
        "tokens_sent": tokens,
    }


def extract_amount(words: list[dict], region: Region, ask) -> dict:
    """`ask(system, text) -> str` is the model call, injected so this runs offline too.

    Returns a row: the value (or None), a status, a confidence, and where on the page it
    came from. Never raises for a missing value — that is a `not_found` outcome, not an error.
    """
    from .fields import FIELDS
    prompt = FIELDS["amount_due"].prompt

    page0 = [w for w in words if w.get("page", 0) == 0]
    cropped = crop(page0, region)
    ctext = as_text(cropped)

    used_fallback = False
    value = ask(prompt, ctext).strip() if ctext.strip() else "NOT_FOUND"
    tokens = len(ctext) // 4

    if value in ("NOT_FOUND", ""):
        # The crop missed it. Send the whole page, not the unsearched remainder — a value
        # straddling the region's edge would be split across the two calls and lost.
        used_fallback = True
        full = as_text(page0)
        value = ask(prompt, full).strip() if full.strip() else "NOT_FOUND"
        tokens += len(full) // 4

    if value in ("NOT_FOUND", ""):
        return _row(None, "not_found", 0.0, None,
                    "no amount due found on the first page", used_fallback,
                    validate_amount(None, page0), tokens)

    box, _ = locate(value, page0)
    checks = validate_amount(value, page0)

    # Hard veto: a value that is not in the page text was invented. Keep it visible but never
    # present it as trusted — it goes to review with the reason, not into the report as fact.
    if any(not c["passed"] for c in checks if c["rule"] in ("present", "in_source_text")):
        return _row(value, "review", 0.0, box,
                    "value not found verbatim in the document text", used_fallback,
                    checks, tokens)

    soft = [c for c in checks if not c["passed"]]
    confidence = CONF_CROP if not used_fallback else CONF_FALLBACK
    if soft:
        confidence = max(0.0, min(confidence, CONF_FALLBACK) - 0.15 * len(soft))

    if not used_fallback and not soft:
        status, reason = "ok", None
    else:
        status = "review"
        reason = (soft[0]["detail"] if soft
                  else "found outside its usual region — worth a glance")

    return _row(value, status, confidence, box, reason, used_fallback, checks, tokens)
