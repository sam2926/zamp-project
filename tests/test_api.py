"""The HTTP contract — what a caller (the frontend, or a reviewer's curl) actually sees.

OCR, the model, and the store are all stubbed, so this runs in milliseconds and never
touches a real key, a real PDF reader, or data/store.db.
"""
import pytest
from fastapi.testclient import TestClient

from api import main, ocr, progress, store

PDF = b"%PDF-1.4 minimal"   # passes the '%PDF' sniff; OCR is mocked anyway


@pytest.fixture
def client(monkeypatch, tmp_path, words):
    monkeypatch.setattr(main, "ALLOW_STUB", True)
    monkeypatch.setattr(ocr, "read", lambda body: (words, 1))
    monkeypatch.setattr(ocr, "warm", lambda: None)
    monkeypatch.setattr(progress, "seed_layouts", lambda: None)
    orig = store.connect
    monkeypatch.setattr(store, "connect", lambda path=None: orig(path or (tmp_path / "s.db")))
    with TestClient(main.app) as c:
        yield c


def _pdf_upload(body=PDF):
    return {"file": ("invoice.pdf", body, "application/pdf")}


def test_health(client):
    assert client.get("/api/health").json()["pipeline"] == "live"


def test_reject_non_pdf(client):
    r = client.post("/api/documents", files={"file": ("note.txt", b"hi", "text/plain")})
    assert r.status_code == 415


def test_reject_oversize(client, monkeypatch):
    monkeypatch.setattr(main, "MAX_UPLOAD_BYTES", 4)
    r = client.post("/api/documents", files=_pdf_upload(b"%PDF-1.4 way too big"))
    assert r.status_code == 413


def test_reject_unreadable(client):
    r = client.post("/api/documents", files=_pdf_upload(b"this is not a pdf"))
    assert r.status_code == 422


def test_keyless_refused_without_stub(client, monkeypatch):
    monkeypatch.setattr(main, "ALLOW_STUB", False)
    r = client.post("/api/documents", files=_pdf_upload())
    assert r.status_code == 400            # no key, no stub → refuse, don't silently run


def test_upload_accepted_with_stub(client):
    r = client.post("/api/documents", files=_pdf_upload())
    assert r.status_code == 201
    body = r.json()
    assert body["status"] == "queued" and body["id"]


def test_empty_report_and_clear(client):
    assert client.get("/api/report.json").json()["rows"] == []
    r = client.post("/api/documents/clear")
    assert r.status_code == 200 and r.json()["ok"] is True


def test_unknown_document_is_404(client):
    assert client.get("/api/documents/nope").status_code == 404


def test_correction_resolves_the_document(client, words):
    # seed a finished, flagged document, then correct it through the API
    job = progress.create_job("apic", "f.pdf", PDF, ask=lambda s, t: "x", live=False)
    job["_words"] = words
    job.update(stage="done", status="review", amount_due="WRONG")
    job["row"] = {"value": "WRONG", "status": "review", "confidence": 0.65, "page": 0,
                  "box": None, "reason": "r", "used_fallback": True, "checks": [], "tokens_sent": 5}

    r = client.patch("/api/documents/apic/fields/amount_due", json={"value": "$1,290.00"})
    assert r.status_code == 200
    assert r.json()["status"] == "ok" and r.json()["located"] is True

    doc = client.get("/api/documents/apic").json()
    assert doc["status"] == "done" and doc["fields"][0]["status"] == "ok"


def test_correction_rejects_empty_value(client):
    progress.create_job("apic2", "f.pdf", PDF, ask=lambda s, t: "x", live=False)
    r = client.patch("/api/documents/apic2/fields/amount_due", json={"value": "   "})
    assert r.status_code == 422


def test_page_render_returns_png(client):
    import fitz
    doc = fitz.open()
    doc.new_page(width=300, height=400)
    pdf_bytes = doc.tobytes()
    doc.close()

    progress.create_job("rend", "f.pdf", pdf_bytes, ask=lambda s, t: "x", live=False)
    r = client.get("/api/documents/rend/page/0")
    assert r.status_code == 200
    assert r.headers["content-type"] == "image/png"
    assert r.content[:8] == b"\x89PNG\r\n\x1a\n"
