"""Staged pipeline runner with per-event DB logging.

Stages (in order):
    fetch → archive → read → extract → verify → review → index → live

Events are written to pipeline_events so the SSE stream can tail them.
The pipeline pauses at 'review' when a document needs human approval.

Public surface
--------------
    run(source_id, mode) -> run_id          # start a pipeline run
    finalize(run_id, doc_id, actor)         # approve a document from review queue
    process(run_id, doc_id)                 # re-usable inner stages (read→verify)
"""
from __future__ import annotations

import asyncio
import pathlib
from datetime import datetime, timezone

import httpx

from . import db
from .chunker import chunk_pages
from .config import ARCHIVE_DIR, SCHEME
from .extractor import extract
from .index import INDEX
from .portal import get_publish_time, list_links, sha256_bytes
from .reader import read_pdf
from .verifier import verify


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _emit(run_id: int, doc_id: int | None, stage: str, status: str, msg: str = "") -> None:
    db.execute(
        """INSERT INTO pipeline_events(run_id, ts, document_id, stage, status, message)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (run_id, db.now(), doc_id, stage, status, msg),
    )


def _finish_run(run_id: int) -> None:
    """Mark the run done if no pending review items remain for it."""
    pending = db.fetchone(
        "SELECT 1 FROM review_queue WHERE run_id = ? AND status = 'pending'",
        (run_id,),
    )
    status = "awaiting_review" if pending else "done"
    db.execute(
        "UPDATE pipeline_runs SET finished_at = ?, status = ? WHERE id = ?",
        (db.now(), status, run_id),
    )


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

async def run(source_id: int, mode: str = "manual") -> int:
    """Fetch the source listing, archive new PDFs, and process each one.

    Returns the run_id.
    """
    src = db.fetchone("SELECT * FROM sources WHERE id = ?", (source_id,))
    if not src:
        raise ValueError(f"Source {source_id} not found")

    run_id = db.execute(
        "INSERT INTO pipeline_runs(started_at, mode, status) VALUES (?, ?, 'running')",
        (db.now(), mode),
    )

    db.execute(
        "UPDATE sources SET last_check = ? WHERE id = ?",
        (db.now(), source_id),
    )

    _emit(run_id, None, "fetch", "start", f"Checking {src['name']}")

    # Derive base URL (strip the listing path so we can resolve relative hrefs)
    listing_url: str = src["url"]
    base_url = listing_url.split("/mock-portal")[0] if "/mock-portal" in listing_url else listing_url

    links = await list_links(listing_url, base_url)

    if not links:
        _emit(run_id, None, "fetch", "done", "No PDF links found on listing page")
        db.execute(
            "UPDATE sources SET last_status = ? WHERE id = ?",
            ("no_links", source_id),
        )
        _finish_run(run_id)
        return run_id

    new_count = 0
    for url in links:
        try:
            async with httpx.AsyncClient(timeout=60) as client:
                resp = await client.get(url)
            blob = resp.content
        except Exception as exc:  # noqa: BLE001
            _emit(run_id, None, "fetch", "error", f"Failed to fetch {url}: {exc}")
            continue

        h = sha256_bytes(blob)

        # Skip if already in DB
        if db.fetchone("SELECT id FROM documents WHERE sha256 = ?", (h,)):
            continue

        new_count += 1

        # Archive the file
        ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
        archive_path = ARCHIVE_DIR / f"{h[:12]}.pdf"
        archive_path.write_bytes(blob)

        filename = url.split("/")[-1]
        doc_id = db.execute(
            """INSERT INTO documents(source_id, url, file_path, sha256, detected_at, status)
               VALUES (?, ?, ?, ?, ?, 'new')""",
            (source_id, url, str(archive_path), h, db.now()),
        )

        db.execute(
            "INSERT INTO notifications(ts, kind, message) VALUES (?, ?, ?)",
            (db.now(), "new_gr", f"New file detected: {filename}"),
        )

        _emit(run_id, doc_id, "fetch",   "done", f"New: {filename}")
        _emit(run_id, doc_id, "archive", "done", f"Saved, sha256 prefix {h[:12]}")

        await _process(run_id, doc_id)

    _emit(run_id, None, "fetch", "done", f"{new_count} new document(s) detected")
    db.execute(
        "UPDATE sources SET last_status = ? WHERE id = ?",
        ("ok", source_id),
    )
    _finish_run(run_id)
    return run_id


# ---------------------------------------------------------------------------
# Inner processing stages (read → extract → verify → queue or auto-finalize)
# ---------------------------------------------------------------------------

async def _process(run_id: int, doc_id: int) -> None:
    """Run stages read → extract → verify for one document."""
    doc = db.fetchone("SELECT * FROM documents WHERE id = ?", (doc_id,))
    if not doc:
        return

    # ── READ ──
    _emit(run_id, doc_id, "read", "start")
    try:
        pages, ocr = await asyncio.to_thread(read_pdf, doc["file_path"])
    except Exception as exc:  # noqa: BLE001
        _emit(run_id, doc_id, "read", "error", str(exc))
        db.execute("UPDATE documents SET status = 'failed' WHERE id = ?", (doc_id,))
        return

    db.executemany(
        "INSERT INTO pages(document_id, page_no, text) VALUES (?, ?, ?)",
        [(doc_id, n, t) for n, t in pages],
    )
    db.executemany(
        "INSERT INTO chunks(document_id, page_no, text) VALUES (?, ?, ?)",
        [(doc_id, pno, text) for pno, text in chunk_pages(pages)],
    )
    db.execute("UPDATE documents SET ocr_used = ? WHERE id = ?", (int(ocr), doc_id))
    _emit(run_id, doc_id, "read", "done",
          f"{len(pages)} pages, OCR {'used' if ocr else 'not needed'}")

    # ── EXTRACT ──
    _emit(run_id, doc_id, "extract", "start")
    try:
        ext = await extract(pages)
    except Exception as exc:  # noqa: BLE001
        _emit(run_id, doc_id, "extract", "error", str(exc))
        db.execute("UPDATE documents SET status = 'failed' WHERE id = ?", (doc_id,))
        return

    db.execute(
        """UPDATE documents SET gr_number=?, gr_date=?, title=?, doc_type=?,
                  scheme=?, department=?, summary_mr=?, summary_en=? WHERE id=?""",
        (ext.gr_number, ext.gr_date, ext.title, ext.doc_type,
         ext.scheme, ext.department, ext.summary_mr, ext.summary_en, doc_id),
    )
    for rule in ext.rules:
        db.execute(
            """INSERT INTO rules(document_id, scheme, field, value, unit,
                   condition_text, source_quote, page_no, effective_from, status)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'draft')""",
            (doc_id, ext.scheme or SCHEME, rule.field, rule.value, rule.unit,
             rule.condition_text, rule.source_quote, rule.page_no, rule.effective_from),
        )
    for ref in ext.refers_to:
        db.execute(
            "INSERT INTO refs(document_id, ref_gr_number, ref_gr_date, relation) VALUES (?,?,?,?)",
            (doc_id, ref.gr_number, ref.gr_date, ref.relation),
        )
    _emit(run_id, doc_id, "extract", "done", f"{len(ext.rules)} rules drafted")

    # ── VERIFY ──
    conf, reasons = verify(ext, pages)

    # Persist grounding flags on each rule
    for rule in ext.rules:
        db.execute(
            "UPDATE rules SET grounded = ? WHERE document_id = ? AND source_quote = ?",
            (int(bool(rule.grounded)), doc_id, rule.source_quote),
        )
    db.execute("UPDATE documents SET confidence = ? WHERE id = ?", (conf, doc_id))
    _emit(run_id, doc_id, "verify", "done", f"Grounding {conf:.0%}")

    # ── ROUTE: human review or auto-finalize ──
    if reasons:
        db.execute(
            "INSERT INTO review_queue(document_id, reason, run_id) VALUES (?, ?, ?)",
            (doc_id, "; ".join(reasons), run_id),
        )
        db.execute("UPDATE documents SET status = 'review' WHERE id = ?", (doc_id,))
        db.execute(
            "INSERT INTO notifications(ts, kind, message) VALUES (?, ?, ?)",
            (db.now(), "review",
             f"Review needed: {ext.gr_number or 'unknown GR'} ({'; '.join(reasons)})"),
        )
        _emit(run_id, doc_id, "review", "waiting", "; ".join(reasons))
        # Pipeline pauses here — finalize() is called when admin approves
    else:
        await finalize(run_id, doc_id, actor="auto")


# ---------------------------------------------------------------------------
# Finalize (approve) — also called from the review API
# ---------------------------------------------------------------------------

async def finalize(run_id: int, doc_id: int, actor: str = "auto") -> None:
    """Approve rules, set document live, rebuild index, emit 'live' event."""

    # Approve only grounded rules
    db.execute(
        "UPDATE rules SET status = 'approved' WHERE document_id = ? AND grounded = 1",
        (doc_id,),
    )
    db.execute(
        "UPDATE documents SET status = 'live', live_at = ? WHERE id = ?",
        (db.now(), doc_id),
    )

    _emit(run_id, doc_id, "review", "done", f"Approved by {actor}")
    _emit(run_id, doc_id, "index",  "start")

    await INDEX.build_async()

    _emit(run_id, doc_id, "index", "done", "Search index updated")

    # Compute freshness metric
    doc = db.fetchone("SELECT detected_at, live_at FROM documents WHERE id = ?", (doc_id,))
    if doc and doc["detected_at"] and doc["live_at"]:
        try:
            det = datetime.fromisoformat(doc["detected_at"])
            liv = datetime.fromisoformat(doc["live_at"])
            minutes = int((liv - det).total_seconds() / 60)
            freshness = f"Detection to answerable: {minutes} min"
        except Exception:  # noqa: BLE001
            freshness = "Answerable now"
    else:
        freshness = "Answerable now"

    _emit(run_id, doc_id, "live", "done", freshness)

    db.execute(
        "INSERT INTO audit_log(ts, actor, action, detail) VALUES (?, ?, ?, ?)",
        (db.now(), actor, "approve", f"document {doc_id}"),
    )

    # Mark the run done if all reviews for this run are resolved
    _finish_run(run_id)
