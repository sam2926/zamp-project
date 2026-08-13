"""The live pipeline worker and the correction path, driven directly (OCR + model stubbed).

This exercises the stage machine and the learn-from-correction flow without the async
queue, so it's deterministic — no polling, no timing.
"""
import asyncio

import pytest

from api import ocr, progress, store


@pytest.fixture
def isolate_store(monkeypatch, tmp_path):
    """Send every store.connect() to a throwaway DB, so tests never touch data/store.db."""
    orig = store.connect
    monkeypatch.setattr(store, "connect", lambda path=None: orig(path or (tmp_path / "s.db")))


def test_work_reads_extracts_and_finishes(monkeypatch, isolate_store, words):
    monkeypatch.setattr(ocr, "read", lambda body: (words, 1))
    job = progress.create_job("j1", "f.pdf", b"%PDF-1.4 x", ask=lambda s, t: "$1,290.00", live=False)
    asyncio.run(progress._work(job))
    assert job["stage"] == "done"
    assert job["status"] == "ok"
    assert job["amount_due"] == "$1,290.00"
    assert job["pages"] == 1
    assert "reading" in job["stage_ms"] and "extracting" in job["stage_ms"]


def test_work_empty_ocr_is_unreadable(monkeypatch, isolate_store):
    monkeypatch.setattr(ocr, "read", lambda body: ([], 1))
    job = progress.create_job("j2", "blank.pdf", b"%PDF x", ask=lambda s, t: "x", live=False)
    asyncio.run(progress._work(job))
    assert job["status"] == "unreadable"


def test_work_ocr_error_is_unreadable_not_a_crash(monkeypatch, isolate_store):
    def boom(body):
        raise ValueError("corrupt pdf")
    monkeypatch.setattr(ocr, "read", boom)
    job = progress.create_job("j3", "bad.pdf", b"not a pdf", ask=lambda s, t: "x", live=False)
    asyncio.run(progress._work(job))
    assert job["status"] == "unreadable"      # a bad file is an outcome, never a 500


def test_apply_correction_resolves_and_learns(isolate_store, words):
    job = progress.create_job("c1", "f.pdf", b"%PDF x", ask=lambda s, t: "x", live=False)
    job["_words"] = words
    job.update(stage="done", status="review", amount_due="WRONG")
    job["row"] = {"value": "WRONG", "status": "review", "confidence": 0.65, "page": 0,
                  "box": None, "reason": "r", "used_fallback": True, "checks": [], "tokens_sent": 5}

    res = progress.apply_correction("c1", "$1,290.00")
    assert res["status"] == "ok"
    assert res["located"] is True             # the value is on the page → its box is learnable
    assert res["region_moved"] is False       # one correction, far below the pattern threshold
    assert job["status"] == "ok" and job["corrected"] is True
    assert job["amount_due"] == "$1,290.00"


def test_report_rows_and_clear(monkeypatch, isolate_store, words):
    monkeypatch.setattr(ocr, "read", lambda body: (words, 1))
    job = progress.create_job("r1", "f.pdf", b"%PDF x", ask=lambda s, t: "$1,290.00", live=False)
    asyncio.run(progress._work(job))

    rows = progress.report_rows()
    assert len(rows) == 1 and rows[0]["file"] == "f.pdf" and rows[0]["amount_due"] == "$1,290.00"

    assert progress.clear() == 1
    assert progress.report_rows() == []
