"""FastAPI app: the live extraction pipeline + the static frontend.

Uploads are real. Each one is validated, queued, and walked through the pipeline by a single
worker (see `api/progress.py`); the front end watches via `GET /api/progress` and pulls the
finished table from `GET /api/report.{json,csv}`.

The model key is the visitor's own, passed per request in the `X-LLM-Key` header and never
stored. With no key and no server-side key, an upload is refused rather than silently run on
a stub — unless ALLOW_STUB=1, which lets the offline stub stand in for local development.
"""
from __future__ import annotations

import os
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, Header, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, PlainTextResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import progress, render
from .model import asker_from_key, echo_asker
from .mock import mock_stats

WEB_DIST = Path(__file__).resolve().parent.parent / "web" / "dist"
MAX_UPLOAD_BYTES = 20 * 1024 * 1024
ALLOW_STUB = os.environ.get("ALLOW_STUB") == "1"

@asynccontextmanager
async def lifespan(app):
    progress.start()          # queue + worker, and warm OCR / seed layouts in the background
    yield


app = FastAPI(title="Invoice extraction", version="0.2.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class FieldPatch(BaseModel):
    value: str


def _resolve_asker(header_key: str | None):
    """Only the visitor's own pasted key ever makes a live call.

    The server deliberately does NOT reach for a key in its own environment — that env key
    belongs to the CLI/eval scripts, where each run is approved. If it leaked into this path,
    the deployed demo would bill the owner for every stranger's upload, which is exactly what
    'bring your own key' exists to prevent. With no header key we return the offline stub;
    the endpoint refuses it unless ALLOW_STUB is set for local development.
    """
    if header_key:
        return asker_from_key(header_key), True
    return echo_asker(), False


# ------------------------------------------------------------------ health

@app.get("/api/health")
def health():
    return {"status": "ok", "pipeline": "live", "ocr_ready": progress.ocr_is_ready()}


# ------------------------------------------------------------------ upload

@app.post("/api/documents", status_code=201)
async def upload(
    file: UploadFile = File(...),
    x_llm_key: Optional[str] = Header(default=None),
):
    if not (file.content_type == "application/pdf" or file.filename.lower().endswith(".pdf")):
        raise HTTPException(415, "That file isn't a PDF. Upload a PDF invoice.")

    body = await file.read()
    if len(body) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, "That PDF is over 20MB. Try a smaller file.")
    if not body.startswith(b"%PDF"):
        raise HTTPException(422, "That PDF couldn't be read — it may be corrupted.")

    ask, live = _resolve_asker(x_llm_key)
    if not live and not ALLOW_STUB:
        raise HTTPException(400, "Add your API key to process an upload.")

    doc_id = uuid.uuid4().hex[:6]
    progress.create_job(doc_id, file.filename, body, ask, live=live)
    await progress.enqueue(doc_id)
    return {"id": doc_id, "filename": file.filename, "status": "queued", "pages": None}


# ------------------------------------------------------------------ live progress

@app.post("/api/documents/clear")
def clear_documents():
    """Reset the session — the job list and the dedup cache. Learning is kept."""
    return {"ok": True, "cleared": progress.clear()}


@app.get("/api/progress")
def live_progress():
    return {
        "jobs": progress.all_jobs(),
        "ocr_ready": progress.ocr_is_ready(),
        "index_ready": progress.index_is_ready(),
    }


# ------------------------------------------------------------------ one document

def _field_status(doc_status: str | None) -> str:
    return {"ok": "ok", "review": "review"}.get(doc_status or "", "missing")


def _document(job: dict) -> dict:
    done = job["stage"] == "done"
    fields = []
    if job["row"]:
        r = job["row"]
        fields = [{
            "name": "amount_due",
            "value": r["value"],
            "confidence": r["confidence"],
            "status": _field_status(job["status"]),
            "page": r["page"],
            "box": r["box"],
            "reason": r["reason"],
        }]
    return {
        "id": job["id"],
        "filename": job["filename"],
        "status": "done" if done else "processing",
        "stage": job["stage"],
        "pages": job["pages"] or 1,
        "layout": {
            "known": job["layout"]["known"],
            "seen_count": job["layout"]["seen_count"],
            "used_template": False,
        },
        "processing": {"model_called": job["model_called"]},
        "fields": fields,
        "line_items": [],
        "validation": [],
    }


@app.get("/api/documents/{doc_id}")
def get_document(doc_id: str):
    job = progress.get(doc_id)
    if job is None:
        raise HTTPException(404, "No document with that id.")
    return _document(job)


@app.get("/api/documents/{doc_id}/page/{page_no}")
def get_page(doc_id: str, page_no: int, width: int = 1200):
    body = progress.page_bytes(doc_id)
    if body is None:
        raise HTTPException(404, "No page image for that document.")
    try:
        png = render.render_page(body, page_no, min(max(width, 200), 2000))
    except Exception:
        raise HTTPException(422, "This page could not be rendered.")
    return Response(png, media_type="image/png",
                    headers={"Cache-Control": "public, max-age=3600"})


@app.patch("/api/documents/{doc_id}/fields/amount_due")
def correct_amount_due(doc_id: str, patch: FieldPatch):
    """A reviewer's answer for a flagged document — recorded, learned from, and resolved."""
    if not patch.value.strip():
        raise HTTPException(422, "Enter the correct amount.")
    result = progress.apply_correction(doc_id, patch.value)
    if result is None:
        raise HTTPException(404, "No document with that id.")
    return result


# ------------------------------------------------------------------ queue + report

@app.get("/api/documents")
def list_documents(limit: int = 100, offset: int = 0):
    jobs = progress.all_jobs()
    items = [{
        "id": j["id"],
        "filename": j["filename"],
        "uploaded": datetime.fromtimestamp(j["created_at"], timezone.utc).isoformat(),
        "vendor": None,
        "total": j["amount_due"],
        "status": j["status"] or j["stage"],
        "min_confidence": j["confidence"],
    } for j in jobs[offset:offset + limit]]
    return {"total": len(jobs), "items": items}


@app.get("/api/report.json")
def report_json():
    return {"rows": progress.report_rows()}


@app.get("/api/report.csv", response_class=PlainTextResponse)
def report_csv():
    import csv
    import io

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["file", "amount_due", "status", "confidence", "page", "reason"])
    for r in progress.report_rows():
        writer.writerow([
            r["file"],
            r["amount_due"] if r["amount_due"] is not None else "NOT_FOUND",
            r["status"], r["confidence"], r["page"], r["reason"] or "",
        ])
    return PlainTextResponse(buf.getvalue(), media_type="text/csv",
                             headers={"Content-Disposition": "attachment; filename=amount_due.csv"})


# ------------------------------------------------------------------ stats (still mock)

@app.get("/api/stats")
def stats():
    return mock_stats()


# ------------------------------------------------------------------ static frontend

if WEB_DIST.is_dir():
    app.mount("/assets", StaticFiles(directory=WEB_DIST / "assets"), name="assets")

    @app.get("/{full_path:path}")
    def spa(full_path: str):
        return FileResponse(WEB_DIST / "index.html")
