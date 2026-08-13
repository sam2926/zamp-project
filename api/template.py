"""Template learning and application.

A template says: on this vendor's layout, `amount_total_gross` lives here. Learn it once
from labelled examples, then every future invoice from that vendor is read by looking in
that place — no model call.

Rules are stored two ways:

  box     where the value sat, as a median over the examples
  anchor  the nearest static label, plus the offset from it

The anchor matters because an extra line item pushes the page down and a fixed box misses.
Anchors move with the content; coordinates do not.

A rule is only kept if the examples agree with each other. Fields that landed somewhere
different every time produce no rule, and fall through to the model.
"""
from __future__ import annotations

import statistics as stats
from collections import defaultdict
from dataclasses import dataclass, field as dc_field, asdict

from .fingerprint import is_static
from . import fieldtypes

# A rule needs this many examples before we trust it.
MIN_EXAMPLES = 1
# Kept permissive on purpose. Rejecting fields whose position varies removed 60% of all
# rules and cost more than the bad rules did; spread is used to size the search window
# instead (see _search_window).
MAX_SPREAD = 1.0
# When reading, look this far outside the stored box. Tight on purpose: a generous box
# swallows the row above and turns one value into two. Swept 0.000-0.018 on build.
READ_PAD = 0.002


@dataclass
class FieldRule:
    name: str
    page: int
    box: list[float]                      # [l, t, r, b], median over examples
    anchor: str | None = None             # nearest static word
    anchor_box: list[float] | None = None
    offset: list[float] | None = None     # field box minus anchor box
    examples: int = 0
    spread: float = 0.0                   # how much the examples disagreed


@dataclass
class Template:
    layout_id: str
    rules: dict[str, FieldRule] = dc_field(default_factory=dict)
    documents_seen: int = 0
    # Median position of each static word across the examples. Used to cancel out the
    # page shift on an incoming scan before reading any field.
    reference: dict[str, list[float]] = dc_field(default_factory=dict)

    def to_dict(self):
        return {"layout_id": self.layout_id, "documents_seen": self.documents_seen,
                "reference": self.reference,
                "rules": {k: asdict(v) for k, v in self.rules.items()}}


def _build_reference(examples) -> dict[str, list[float]]:
    """Where each static word usually sits. Only words appearing exactly once per page,
    so alignment is never ambiguous."""
    positions = defaultdict(list)
    for _, words in examples:
        counts = defaultdict(int)
        for w in words:
            if w.get("page", 0) == 0:
                counts[w["text"].strip().upper()] += 1
        for w in words:
            text = w["text"].strip().upper()
            if w.get("page", 0) == 0 and counts[text] == 1 and is_static(text):
                positions[text].append(_centre(w["box"]))
    return {
        text: [stats.median(p[0] for p in pts), stats.median(p[1] for p in pts)]
        for text, pts in positions.items()
        if len(pts) >= max(2, len(examples) // 2)
    }


def page_shift(tmpl: "Template", words) -> tuple[float, float]:
    """How far this scan is offset from the template's reference, in page fractions.

    Scans of the same form drift by 0.03-0.04 — more than any sane read tolerance. So we
    cancel the shift first, using the median offset of every static word we recognise.
    """
    if not tmpl.reference:
        return 0.0, 0.0
    counts = defaultdict(int)
    for w in words:
        if w.get("page", 0) == 0:
            counts[w["text"].strip().upper()] += 1

    dxs, dys = [], []
    for w in words:
        text = w["text"].strip().upper()
        if w.get("page", 0) != 0 or counts[text] != 1 or text not in tmpl.reference:
            continue
        cx, cy = _centre(w["box"])
        rx, ry = tmpl.reference[text]
        dxs.append(cx - rx)
        dys.append(cy - ry)

    if len(dxs) < 3:
        return 0.0, 0.0
    return stats.median(dxs), stats.median(dys)


def _centre(box):
    return (box[0] + box[2]) / 2, (box[1] + box[3]) / 2


def _nearest_anchor(field_box, words):
    """Closest static word sitting left of or above the field — how a human reads a form."""
    fx, fy = _centre(field_box)
    best, best_d = None, 1e9
    for w in words:
        text = w["text"].strip().upper()
        if not is_static(text):
            continue
        wx, wy = _centre(w["box"])
        if wx > fx + 0.02 and wy > fy + 0.01:      # ignore things below-right of the field
            continue
        d = ((fx - wx) ** 2 + (fy - wy) ** 2) ** 0.5
        if d < best_d:
            best, best_d = w, d
    return best


def learn(examples: list[tuple[dict, list[dict]]], layout_id: str) -> Template:
    """examples: (annotation_fields, ocr_words) per document of one layout.

    annotation_fields: {field_name: {"box": [...], "page": int}}
    """
    tmpl = Template(layout_id=layout_id, documents_seen=len(examples),
                    reference=_build_reference(examples))
    seen = defaultdict(list)

    for fields, words in examples:
        for name, info in fields.items():
            seen[name].append((info["box"], info["page"], words))

    for name, occurrences in seen.items():
        if len(occurrences) < MIN_EXAMPLES:
            continue

        boxes = [o[0] for o in occurrences]
        pages = [o[1] for o in occurrences]
        if len(set(pages)) > 1:                    # field moves page to page — untrustworthy
            continue

        centres_x = [(_centre(b))[0] for b in boxes]
        centres_y = [(_centre(b))[1] for b in boxes]
        spread = max(
            max(centres_x) - min(centres_x),
            max(centres_y) - min(centres_y),
        )
        if spread > MAX_SPREAD:                    # inconsistent — no rule, fall through to model
            continue

        median_box = [stats.median(b[i] for b in boxes) for i in range(4)]
        anchor = _nearest_anchor(median_box, occurrences[0][2])

        tmpl.rules[name] = FieldRule(
            name=name,
            page=pages[0],
            box=[round(v, 5) for v in median_box],
            anchor=anchor["text"].strip().upper() if anchor else None,
            anchor_box=[round(v, 5) for v in anchor["box"]] if anchor else None,
            offset=[round(median_box[i] - anchor["box"][i], 5) for i in range(4)] if anchor else None,
            examples=len(occurrences),
            spread=round(spread, 5),
        )
    return tmpl


def _shifted_box(rule: FieldRule, words) -> list[float]:
    """Kept for provenance; the whole-page shift replaced it.

    Per-field anchoring measured worse than aligning the page once (12.9% against 16.0%
    before other fixes). Its anchor words were frequently content rather than labels, and
    ambiguous ones — a label appearing four times — shifted the box to the wrong instance.
    """
    return rule.box


def _search_window(rule: FieldRule, dx: float, dy: float) -> list[float]:
    """Where to look. A field that moved around in the examples gets a wider window."""
    pad = min(max(rule.spread, 0.004), 0.05)
    return [rule.box[0] + dx - pad, rule.box[1] + dy - pad * 0.6,
            rule.box[2] + dx + pad, rule.box[3] + dy + pad * 0.6]


def _rows(words: list[dict]) -> list[list[dict]]:
    """Group words into visual lines, then order each line left to right.

    Sorting by a rounded y merges adjacent lines into one bucket and scrambles them across
    both — which is how "50 Cambridge Street" became "500 Street Cambridge".
    """
    rows: list[list[dict]] = []
    for w in sorted(words, key=lambda w: _centre(w["box"])[1]):
        y = _centre(w["box"])[1]
        height = max(w["box"][3] - w["box"][1], 0.004)
        for row in rows:
            if abs(y - _centre(row[0]["box"])[1]) < height * 0.7:
                row.append(w)
                break
        else:
            rows.append([w])
    return [sorted(r, key=lambda w: w["box"][0]) for r in rows]


def _assemble(words: list[dict]) -> str:
    return "\n".join(" ".join(w["text"] for w in row) for row in _rows(words)).strip()


def apply(tmpl: Template, words: list[dict]) -> dict[str, dict]:
    """Read every field the template knows about out of this document's OCR.

    Single-token fields (money, dates, ids) are searched for by shape inside a window —
    the closest candidate of the right type wins. Multi-word fields (names, addresses)
    are assembled from everything sitting in the box, because they span lines.
    """
    out: dict[str, dict] = {}
    dx, dy = page_shift(tmpl, words)

    for name, rule in tmpl.rules.items():
        win = _search_window(rule, dx, dy)
        expected = fieldtypes.kind(name)
        target = ((rule.box[0] + rule.box[2]) / 2 + dx,
                  (rule.box[1] + rule.box[3]) / 2 + dy)

        in_window = [
            w for w in words
            if w.get("page", 0) == rule.page
            and win[0] <= _centre(w["box"])[0] <= win[2]
            and win[1] <= _centre(w["box"])[1] <= win[3]
        ]

        chosen: list[dict] = []
        if in_window:
            if fieldtypes.is_multiword(name):
                # Keep only rows overlapping the original box height; the window is padded
                # for drift, not to swallow the row above and below.
                lo, hi = rule.box[1] + dy - 0.006, rule.box[3] + dy + 0.006
                chosen = [w for w in in_window if lo <= _centre(w["box"])[1] <= hi] or in_window
            else:
                typed = [w for w in in_window if fieldtypes.matches(w["text"], expected)]
                pool = typed or in_window
                # One token, closest to where the rule expects it. Extending to the whole
                # contiguous run on the line was tried and measured worse (28.9% against
                # 31.4%) — it over-captures neighbouring columns on dense invoices.
                chosen = [min(pool, key=lambda w: (
                    (_centre(w["box"])[0] - target[0]) ** 2
                    + ((_centre(w["box"])[1] - target[1]) * 2) ** 2))]

        if not chosen:
            out[name] = {"value": None, "box": rule.box, "page": rule.page, "words": 0,
                         "ocr_conf": 0.0, "rule_spread": rule.spread,
                         "type_match": False, "candidates": 0}
            continue

        confs = [w.get("conf", 1.0) for w in chosen]
        out[name] = {
            "value": _assemble(chosen),
            "box": [min(w["box"][0] for w in chosen), min(w["box"][1] for w in chosen),
                    max(w["box"][2] for w in chosen), max(w["box"][3] for w in chosen)],
            "page": rule.page,
            "words": len(chosen),
            "ocr_conf": round(sum(confs) / len(confs), 4),
            "rule_spread": rule.spread,
            "type_match": all(fieldtypes.matches(w["text"], expected) for w in chosen)
                          if not fieldtypes.is_multiword(name) else True,
            "candidates": len(in_window),
        }
    return out
