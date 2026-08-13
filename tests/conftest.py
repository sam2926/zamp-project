"""Shared fixtures. No heavy imports here — the suite never loads torch/docTR."""
from __future__ import annotations

import pytest

from api import progress


@pytest.fixture
def words() -> list[dict]:
    """A tiny one-page invoice. The header and 'BILL TO' sit top-left (outside the
    amount_due region); the totals block — including the amount — sits bottom-right,
    inside it. So a crop over the region sees the total but not the header."""
    return [
        {"text": "INVOICE", "box": [0.10, 0.05, 0.30, 0.08], "page": 0, "conf": 0.99},
        {"text": "BILL", "box": [0.10, 0.20, 0.17, 0.23], "page": 0, "conf": 0.98},
        {"text": "TO", "box": [0.18, 0.20, 0.23, 0.23], "page": 0, "conf": 0.98},
        {"text": "ACME", "box": [0.10, 0.24, 0.22, 0.27], "page": 0, "conf": 0.97},
        {"text": "TOTAL", "box": [0.68, 0.90, 0.80, 0.93], "page": 0, "conf": 0.99},
        {"text": "DUE", "box": [0.81, 0.90, 0.88, 0.93], "page": 0, "conf": 0.99},
        {"text": "$1,290.00", "box": [0.82, 0.905, 0.95, 0.93], "page": 0, "conf": 0.96},
    ]


@pytest.fixture(autouse=True)
def _reset_progress():
    """Keep the in-memory job list from leaking between tests. Touches only memory —
    never the SQLite store (so nothing here writes to data/store.db)."""
    progress._jobs.clear()
    progress._order.clear()
    yield
    progress._jobs.clear()
    progress._order.clear()
