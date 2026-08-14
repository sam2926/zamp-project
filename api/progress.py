"""The live pipeline: one worker, one document at a time, walking the stages.

Every upload becomes a job and joins a queue. A single worker pulls them one at a time and
moves each through the stages below, stamping how long each took. One worker is not a
limitation dressed up as a virtue — docTR is not parallel on CPU anyway — and it makes the
live view honest: while one document is `reading`, the rest genuinely sit `queued`.

The blocking work (OCR, the model call) runs in a threadpool so the event loop stays free to
answer the `GET /api/progress` polls the front end makes every second.

State lives in memory. Final results are cached in SQLite (so a re-upload of the same bytes
skips the model entirely), but the in-flight progress is ephemeral: if the process restarts,
whatever was mid-flight is simply re-uploaded. That is the right trade for a live view.

There is no `failed` terminal state. Every document ends `done`; the outcome it carries is
one of ok · review · not_found · unreadable, and `unreadable` is where a genuine processing
error goes — distinct from an invoice that simply has no amount due on it.
"""
from __future__ import annotations

import asyncio
import json
import threading
import time
from pathlib import Path

from . import ocr, pipeline, relearn, store
from .extract import locate
from .fields import FIELDS
from .fingerprint import LayoutIndex, signature
from .region import density_boxes, load as load_region

STAGES = ["queued", "reading", "matching", "extracting", "checking", "done"]
PIPELINE_TAG = "amount_due_80_v3"        # bump when a change would alter the cached answer

CACHE = Path("data/ocr_cache")
_region = load_region(FIELDS["amount_due"].region_path)
# The training baseline lives in its own immutable file. Relearn always folds corrections
# into this, never into a region that already absorbed earlier corrections — so corrections
# describe the original distribution and can never compound across restarts.
_ORIGINAL_BOXES = density_boxes(load_region(FIELDS["amount_due"].base_region_path))

_jobs: dict[str, dict] = {}
_order: list[str] = []
_lock = threading.Lock()

_queue: asyncio.Queue | None = None

# Known layouts, seeded from our OCR cache in the background at startup.
_index = LayoutIndex()
_layout_counts: dict[str, int] = {}
_layout_counts_seeded: set[str] = set()
_index_ready = False


# ------------------------------------------------------------------ layout seeding

def seed_layouts() -> None:
    """Learn the layouts we already know from the OCR cache, so an uploaded invoice from a
    familiar vendor can be recognised. One signature per layout cluster; the count of
    documents in that cluster becomes the 'seen N times' badge."""
    global _index_ready
    if not CACHE.exists():
        _index_ready = True
        return
    for f in CACHE.glob("*.json"):
        try:
            doc = json.loads(f.read_text())
        except Exception:
            continue
        cluster = doc.get("cluster_id")
        key = str(cluster) if cluster is not None else f.stem
        _layout_counts[key] = _layout_counts.get(key, 0) + 1
        if key not in _layout_counts_seeded:
            words = [{"text": w["text"], "box": w["box"], "page": p["page_idx"]}
                     for p in doc["pages"] for w in p["words"]]
            _index.add(key, signature(words))
            _layout_counts_seeded.add(key)
    _index_ready = True


def _match_layout(words: list[dict]) -> tuple[bool, int]:
    if not _index_ready or len(_index) == 0:
        return False, 0
    m = _index.match(signature(words))
    return (m.known, _layout_counts.get(m.layout_id, 0) if m.known else 0)


# ------------------------------------------------------------------ job lifecycle

def _now() -> float:
    return time.time()


def create_job(job_id: str, filename: str, pdf_bytes: bytes, ask, live: bool = True) -> dict:
    job = {
        "id": job_id,
        "filename": filename,
        "pages": None,
        "stage": "queued",
        "status": None,                  # ok · review · not_found · unreadable, set at done
        "corrected": False,              # true once a human has supplied the value
        "amount_due": None,
        "confidence": None,
        "reason": None,
        "layout": {"known": None, "seen_count": 0},
        "model_called": None,
        "created_at": _now(),
        "started_at": None,
        "finished_at": None,
        "stage_ms": {},
        "row": None,
        # private, never serialised to the client:
        "_bytes": pdf_bytes,
        "_ask": ask,
        "_live": live,
        "_sha": store.file_hash(pdf_bytes),
    }
    with _lock:
        _jobs[job_id] = job
        _order.append(job_id)
    return job


def _set_stage(job: dict, stage: str) -> None:
    with _lock:
        job["stage"] = stage
        job.setdefault("_stage_started", {})[stage] = _now()
        if stage == "reading" and job["started_at"] is None:
            job["started_at"] = _now()


def _record_ms(job: dict, stage: str) -> None:
    started = job.get("_stage_started", {}).get(stage)
    if started is not None:
        job["stage_ms"][stage] = int((_now() - started) * 1000)


def _finish(job: dict, status: str, row: dict | None, reason: str | None,
            model_called: bool) -> None:
    with _lock:
        job["stage"] = "done"
        job["status"] = status
        job["row"] = row
        job["amount_due"] = row["value"] if row else None
        job["confidence"] = row["confidence"] if row else None
        job["reason"] = reason if reason is not None else (row["reason"] if row else None)
        job["model_called"] = model_called
        job["finished_at"] = _now()


async def _work(job: dict) -> None:
    ask = job["_ask"]

    # A literal re-upload never pays twice: same bytes, same pipeline → serve the stored
    # answer with no OCR and no model call. This is the honest 'cost nothing' path.
    cached = await asyncio.to_thread(_lookup_cache, job["_sha"])
    if cached is not None:
        job["pages"] = cached.get("pages")
        job["layout"] = cached.get("layout", job["layout"])
        _finish(job, cached["status"], cached["row"], None, model_called=False)
        return

    _set_stage(job, "reading")
    try:
        words, pages = await asyncio.to_thread(ocr.read, job["_bytes"])
    except Exception:
        _record_ms(job, "reading")
        _finish(job, "unreadable", None, "this PDF could not be read", model_called=False)
        return
    job["pages"] = pages
    job["_words"] = words          # kept so a later correction can locate the right value
    _record_ms(job, "reading")

    if not words:
        _finish(job, "unreadable", None, "no text could be read from this PDF",
                model_called=False)
        return

    _set_stage(job, "matching")
    known, seen = _match_layout(words)
    with _lock:
        job["layout"] = {"known": known, "seen_count": seen}
    _record_ms(job, "matching")

    _set_stage(job, "extracting")
    try:
        row = await asyncio.to_thread(pipeline.extract_amount, words, _region, ask)
    except Exception as exc:
        _record_ms(job, "extracting")
        _finish(job, "unreadable", None,
                f"the reading model could not be reached — check your API key ({_short(exc)})",
                model_called=False)
        return
    _record_ms(job, "extracting")

    _set_stage(job, "checking")            # checks ran inside extract; this is the UI beat
    _record_ms(job, "checking")

    _finish(job, row["status"], row, None, model_called=True)
    # Only real model answers are cached. A stub (offline dev) result must never be stored,
    # or it would be served back to a later paid run of the same file — a silent poisoning.
    if job.get("_live"):
        await asyncio.to_thread(_store_cache, job)


def _short(exc: Exception) -> str:
    return repr(exc)[:120]


# ------------------------------------------------------------------ dedup cache

def _lookup_cache(sha: str) -> dict | None:
    conn = store.connect()
    try:
        cached = store.get_cached(conn, sha)
        if cached and cached.get("pipeline") == PIPELINE_TAG:
            return cached
        return None
    finally:
        conn.close()


def _store_cache(job: dict) -> None:
    conn = store.connect()
    try:
        store.put_cached(conn, job["_sha"], job["filename"], {
            "pipeline": PIPELINE_TAG,
            "status": job["status"],
            "row": job["row"],
            "pages": job["pages"],
            "layout": job["layout"],
        })
    finally:
        conn.close()


# ------------------------------------------------------------------ worker + queue

async def _worker() -> None:
    assert _queue is not None
    while True:
        job_id = await _queue.get()
        try:
            await _work(_jobs[job_id])
        except Exception:
            job = _jobs.get(job_id)
            if job and job["status"] is None:
                _finish(job, "unreadable", None, "an unexpected error occurred",
                        model_called=False)
        finally:
            _queue.task_done()


def start() -> None:
    """Called on FastAPI startup, inside the running event loop."""
    global _queue
    _queue = asyncio.Queue()
    asyncio.create_task(_worker())
    threading.Thread(target=ocr.warm, daemon=True).start()
    threading.Thread(target=seed_layouts, daemon=True).start()


async def enqueue(job_id: str) -> None:
    assert _queue is not None
    await _queue.put(job_id)


# ------------------------------------------------------------------ views

def _public(job: dict) -> dict:
    return {k: v for k, v in job.items() if not k.startswith("_")}


def ocr_is_ready() -> bool:
    return ocr.ready()


def index_is_ready() -> bool:
    return _index_ready


def get(job_id: str) -> dict | None:
    job = _jobs.get(job_id)
    return _public(job) if job else None


def all_jobs() -> list[dict]:
    """Newest first — the live list and the report both read from here."""
    with _lock:
        return [_public(_jobs[i]) for i in reversed(_order)]


def report_rows() -> list[dict]:
    """One row per uploaded document: the value, or null, plus how much to trust it."""
    rows = []
    for job in reversed(_order):
        j = _jobs[job]
        rows.append({
            "file": j["filename"],
            "amount_due": j["amount_due"],
            "status": j["status"] or j["stage"],
            "confidence": j["confidence"],
            "page": j["row"]["page"] if j["row"] else None,
            "box": j["row"]["box"] if j["row"] else None,
            "reason": j["reason"],
        })
    return rows


def page_bytes(job_id: str) -> bytes | None:
    """The stored PDF bytes for rendering the page a reviewer looks at."""
    job = _jobs.get(job_id)
    return job.get("_bytes") if job else None


def clear() -> int:
    """Wipe the session: the in-memory job list and the dedup cache, so a new run starts
    clean and re-reads its files. Learned corrections and the known-layout index are kept —
    those are what the system has learned, not this session's scratch state."""
    with _lock:
        n = len(_jobs)
        _jobs.clear()
        _order.clear()
    conn = store.connect()
    try:
        store.clear_cache(conn)
    finally:
        conn.close()
    return n


def apply_correction(job_id: str, value: str) -> dict | None:
    """A human's answer for a flagged document.

    Records the correction and — the valuable part — *where the right value sits on the
    page*, which is evidence about every invoice shaped like this one. The region re-learns
    only once enough corrections form a pattern (see relearn.MIN_CORRECTIONS); a single
    reviewer's answer never drags it. The document is then resolved and leaves the queue.
    """
    job = _jobs.get(job_id)
    if job is None:
        return None

    value = value.strip()
    was = job.get("amount_due")
    page0 = [w for w in (job.get("_words") or []) if w.get("page", 0) == 0]
    box, _ = locate(value, page0) if page0 else (None, 0.0)

    conn = store.connect()
    try:
        store.record_correction(conn, job["_sha"], "amount_due", was, value, box)
        count = len(store.correction_boxes(conn, "amount_due"))
        region_moved = False
        if relearn.should_relearn(conn, "amount_due"):
            try:
                global _region
                _region, _ = relearn.relearn(
                    "amount_due", _ORIGINAL_BOXES, FIELDS["amount_due"].region_path,
                    FIELDS["amount_due"].coverage, conn)
                region_moved = True
            except Exception:
                region_moved = False
    finally:
        conn.close()

    with _lock:
        job["status"] = "ok"
        job["corrected"] = True
        job["amount_due"] = value
        job["confidence"] = 1.0
        job["reason"] = None
        if job["row"]:
            job["row"].update(value=value, status="ok", confidence=1.0, reason=None,
                              box=box or job["row"].get("box"))

    return {
        "value": value,
        "status": "ok",
        "located": box is not None,
        "corrections": count,
        "threshold": relearn.MIN_CORRECTIONS,
        "region_moved": region_moved,
    }
