"""Realistic mock responses matching API.md.

Deliberately not clean: one field fails validation, one was repaired, one is missing.
The frontend must handle all four statuses, so the mock shows all four.
"""
from __future__ import annotations

import random


def mock_document(doc_id: str, filename: str) -> dict:
    return {
        "id": doc_id,
        "filename": filename,
        "status": "done",
        "pages": 1,
        "layout": {"known": True, "seen_count": 47, "used_template": True},
        "processing": {"ms": 340, "model_called": False},
        "fields": [
            _f("vendor_name", "ACME SUPPLY CO", 0.97, "ok", [0.09, 0.12, 0.41, 0.15]),
            _f("vendor_address", "1200 INDUSTRIAL PKWY\nCOLUMBUS, OH 43228",
               0.93, "ok", [0.09, 0.16, 0.41, 0.23]),
            _f("document_id", "INV-99304502", 0.99, "ok", [0.78, 0.12, 0.91, 0.14]),
            _f("date_issue", "2026-03-25", 0.96, "ok", [0.78, 0.15, 0.89, 0.17]),
            _f("customer_billing_name", "Starcom Media Services", 0.95, "ok",
               [0.09, 0.28, 0.40, 0.30]),
            _f("amount_total_net", "1190.00", 0.94, "ok", [0.78, 0.30, 0.88, 0.32]),
            _f("amount_total_tax", "100.00", 0.92, "ok", [0.78, 0.32, 0.88, 0.34]),
            _f("amount_total_gross", "1290.00", 0.62, "review", [0.78, 0.34, 0.88, 0.36],
               reason="line items sum to 1190.00, not 1290.00"),
            _f("address__postcode", "OL3 5DE", 0.88, "repaired", [0.09, 0.18, 0.22, 0.20],
               reason="postcodes cannot begin with a digit; one substitution fixes it",
               original="0L3 5DE"),
            _f("payment_terms", None, 0.0, "missing", None,
               reason="not found on any page"),
        ],
        "line_items": [
            {
                "id": 1,
                "fields": [
                    _f("description", "Widget, 40mm brushed", 0.94, "ok", [0.10, 0.52, 0.38, 0.54]),
                    _f("quantity", "12", 0.91, "ok", [0.42, 0.52, 0.46, 0.54]),
                    _f("unit_price_gross", "45.00", 0.93, "ok", [0.60, 0.52, 0.68, 0.54]),
                    _f("amount_gross", "540.00", 0.90, "ok", [0.78, 0.52, 0.88, 0.54]),
                ],
            },
            {
                "id": 2,
                "fields": [
                    _f("description", "Mounting bracket", 0.89, "ok", [0.10, 0.55, 0.38, 0.57]),
                    _f("quantity", "1O", 0.54, "review", [0.42, 0.55, 0.46, 0.57],
                       reason="readers disagree: '10' or '1O'"),
                    _f("unit_price_gross", "65.00", 0.92, "ok", [0.60, 0.55, 0.68, 0.57]),
                    _f("amount_gross", "650.00", 0.91, "ok", [0.78, 0.55, 0.88, 0.57]),
                ],
            },
        ],
        "validation": [
            {"rule": "line_items_sum_to_total", "passed": False,
             "detail": "Σ line items 1190.00 ≠ total 1290.00",
             "suspect_fields": ["amount_total_gross"]},
            {"rule": "net_plus_tax_equals_gross", "passed": True},
            {"rule": "quantity_x_price_equals_amount", "passed": True},
            {"rule": "issue_date_before_due_date", "passed": True},
        ],
    }


def _f(name, value, confidence, status, box, reason=None, original=None) -> dict:
    field = {"name": name, "value": value, "confidence": confidence,
             "status": status, "page": 0, "box": box}
    if reason:
        field["reason"] = reason
    if original:
        field["original"] = original
    return field


def mock_queue(limit: int, offset: int, needs_review, sort: str) -> dict:
    random.seed(11)
    vendors = ["ACME SUPPLY CO", "NORTHWIND TRADING", "CITY COMPTROLLER",
               "Starcom Media Services", "BLUE RIDGE PAPER", "HALCYON LOGISTICS"]
    items = []
    for i in range(60):
        review = random.choice([0, 0, 0, 1, 2, 3])
        if needs_review is True and review == 0:
            continue
        if needs_review is False and review > 0:
            continue
        items.append({
            "id": f"{i:06x}",
            "filename": f"invoice-{2000 + i}.pdf",
            "uploaded": f"2026-08-{(i % 28) + 1:02d}T09:{i % 60:02d}:00Z",
            "vendor": random.choice(vendors),
            "total": f"{random.randint(80, 9000)}.{random.choice(['00', '50', '25'])}",
            "fields_ok": 19 - review,
            "fields_review": review,
            "min_confidence": round(random.uniform(0.45, 0.99), 2),
        })
    if sort == "confidence":
        items.sort(key=lambda x: x["min_confidence"])
    return {"total": len(items), "items": items[offset:offset + limit]}


def mock_stats() -> dict:
    return {
        "documents": 1500,
        "deterministic_coverage": 0.81,
        "auto_accepted": 0.74,
        "calibration": [
            {"bucket": "0.9–1.0", "predicted": 0.95, "actual": 0.94, "n": 8200},
            {"bucket": "0.8–0.9", "predicted": 0.85, "actual": 0.83, "n": 2100},
            {"bucket": "0.7–0.8", "predicted": 0.75, "actual": 0.72, "n": 1400},
            {"bucket": "0.5–0.7", "predicted": 0.60, "actual": 0.58, "n": 900},
            {"bucket": "0.0–0.5", "predicted": 0.30, "actual": 0.34, "n": 400},
        ],
        "per_field": [
            {"field": "vendor_name", "n": 338, "f1": 0.91},
            {"field": "document_id", "n": 336, "f1": 0.95},
            {"field": "date_issue", "n": 330, "f1": 0.93},
            {"field": "amount_total_gross", "n": 331, "f1": 0.88},
            {"field": "amount_due", "n": 325, "f1": 0.87},
            {"field": "vendor_address", "n": 320, "f1": 0.79},
            {"field": "line_item_description", "n": 2810, "f1": 0.74},
            {"field": "line_item_amount_gross", "n": 2340, "f1": 0.81},
        ],
        "by_layout": {"seen": {"f1": 0.93, "n": 268}, "unseen": {"f1": 0.71, "n": 70}},
    }
