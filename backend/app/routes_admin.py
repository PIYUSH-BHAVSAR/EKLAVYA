"""Admin API routes — all require the 'admin' role."""
from __future__ import annotations

import asyncio
import json
import shutil
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from . import db
from .auth import require_admin
from .config import ARCHIVE_DIR, DB_PATH, PDFS_HELD, PDFS_SEED, PORTAL_PUB, SCHEME
from .eval import run_eval
from .guardrails import set_kill_switch
from .pipeline import finalize, run as pipeline_run
from .portal import publish_next
from .rules import all_fields, current_rules, history as rule_history

router = APIRouter(prefix="/admin")


# ---------------------------------------------------------------------------
# Overview
# ---------------------------------------------------------------------------

@router.get("/overview")
def overview(request: Request):
    require_admin(request)

    docs_live = db.fetchone("SELECT COUNT(*) AS n FROM documents WHERE status='live'")["n"]
    sources_total = db.fetchone("SELECT COUNT(*) AS n FROM sources WHERE enabled=1")["n"]
    sources_ok = db.fetchone("SELECT COUNT(*) AS n FROM sources WHERE enabled=1 AND last_status='ok'")["n"]
    review_pending = db.fetchone("SELECT COUNT(*) AS n FROM review_queue WHERE status='pending'")["n"]

    today = datetime.now(timezone.utc).date().isoformat()
    questions_today = db.fetchone(
        "SELECT COUNT(*) AS n FROM queries WHERE ts >= ?", (today,))["n"]
    refused_today = db.fetchone(
        "SELECT COUNT(*) AS n FROM queries WHERE ts >= ? AND refused=1", (today,))["n"]
    total_today = questions_today or 1
    refusal_rate = round(refused_today / total_today * 100, 1)

    avg_latency = db.fetchone(
        "SELECT AVG(latency_ms) AS v FROM queries WHERE ts >= ?", (today,))["v"]

    # Last detection-to-live time (from most recent live document)
    last_doc = db.fetchone(
        "SELECT detected_at, live_at FROM documents WHERE status='live' ORDER BY live_at DESC LIMIT 1")
    freshness_min = None
    if last_doc and last_doc["detected_at"] and last_doc["live_at"]:
        try:
            det = datetime.fromisoformat(last_doc["detected_at"])
            liv = datetime.fromisoformat(last_doc["live_at"])
            freshness_min = int((liv - det).total_seconds() / 60)
        except Exception:
            pass

    # Latest eval score
    eval_run = db.fetchone(
        "SELECT total, passed FROM eval_runs ORDER BY ts DESC LIMIT 1")
    eval_score = None
    if eval_run and eval_run["total"]:
        eval_score = f"{eval_run['passed']}/{eval_run['total']}"

    # Recent activity (last 10 audit + pipeline events)
    recent = db.fetchall(
        "SELECT ts, actor AS who, action, detail AS msg FROM audit_log ORDER BY ts DESC LIMIT 10")

    return {
        "docs_live": docs_live,
        "sources_healthy": f"{sources_ok} of {sources_total}",
        "review_pending": review_pending,
        "questions_today": questions_today,
        "refusal_rate_pct": refusal_rate,
        "avg_latency_ms": round(avg_latency or 0),
        "freshness_min": freshness_min,
        "eval_score": eval_score,
        "recent_activity": [dict(r) for r in recent],
    }


# ---------------------------------------------------------------------------
# Sources
# ---------------------------------------------------------------------------

@router.get("/sources")
def sources(request: Request):
    require_admin(request)
    rows = db.fetchall("SELECT * FROM sources ORDER BY id")
    return [dict(r) for r in rows]


@router.post("/sources/{source_id}/toggle")
def toggle_source(source_id: int, request: Request):
    require_admin(request)
    src = db.fetchone("SELECT enabled FROM sources WHERE id=?", (source_id,))
    if not src:
        raise HTTPException(404, "Source not found")
    new = 1 - src["enabled"]
    db.execute("UPDATE sources SET enabled=? WHERE id=?", (new, source_id))
    db.execute("INSERT INTO audit_log(ts,actor,action,detail) VALUES (?,?,?,?)",
               (db.now(), _actor(request), "toggle_source", f"source {source_id} -> {new}"))
    return {"enabled": bool(new)}


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------

@router.post("/pipeline/run")
async def pipeline_start(request: Request, background_tasks: BackgroundTasks):
    require_admin(request)
    body = await request.json()
    source_id = body.get("source_id", 1)
    src = db.fetchone("SELECT id FROM sources WHERE id=?", (source_id,))
    if not src:
        raise HTTPException(404, "Source not found")

    # Create run record first so the client has an id to stream immediately
    run_id = db.execute(
        "INSERT INTO pipeline_runs(started_at, mode, status) VALUES (?,?,?)",
        (db.now(), "manual", "running"),
    )

    async def _bg():
        # Override the auto-created run in pipeline.run() by passing it an existing run_id
        # We use the existing run_id by running _process directly for each new doc
        from .pipeline import run as _run
        await _run(source_id, mode="manual")

    background_tasks.add_task(_bg)
    return {"run_id": run_id}


@router.get("/pipeline/stream")
async def pipeline_stream(run_id: int, request: Request):
    """SSE endpoint: streams pipeline_events for a run_id."""
    # Token auth via query param (EventSource cannot set headers)
    from .auth import get_current_user
    user = get_current_user(request)
    if not user or user["role"] != "admin":
        raise HTTPException(401, "Admin auth required")

    async def _gen():
        last_id = 0
        idle_ticks = 0
        while True:
            rows = db.fetchall(
                "SELECT * FROM pipeline_events WHERE run_id=? AND id>? ORDER BY id",
                (run_id, last_id),
            )
            for row in rows:
                last_id = row["id"]
                idle_ticks = 0
                yield f"data: {json.dumps(dict(row))}\n\n"

            run_row = db.fetchone("SELECT status FROM pipeline_runs WHERE id=?", (run_id,))
            if run_row and run_row["status"] in ("done", "failed"):
                yield f'data: {{"stage":"end","status":"{run_row["status"]}"}}\n\n'
                break

            idle_ticks += 1
            if idle_ticks > 300:   # 2 minutes with no event → give up
                yield 'data: {"stage":"end","status":"timeout"}\n\n'
                break

            yield ": keepalive\n\n"
            await asyncio.sleep(0.4)

    return StreamingResponse(_gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@router.get("/pipeline/runs")
def pipeline_runs(request: Request, limit: int = 20):
    require_admin(request)
    rows = db.fetchall(
        "SELECT * FROM pipeline_runs ORDER BY started_at DESC LIMIT ?", (limit,))
    return [dict(r) for r in rows]


@router.get("/pipeline/runs/{run_id}/events")
def pipeline_events(run_id: int, request: Request):
    require_admin(request)
    rows = db.fetchall(
        "SELECT * FROM pipeline_events WHERE run_id=? ORDER BY id", (run_id,))
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Demo controls
# ---------------------------------------------------------------------------

@router.post("/demo/publish-next")
def demo_publish_next(request: Request):
    require_admin(request)
    filename = publish_next()
    if not filename:
        raise HTTPException(404, "No held PDFs remaining")
    db.execute("INSERT INTO audit_log(ts,actor,action,detail) VALUES (?,?,?,?)",
               (db.now(), _actor(request), "publish_next", filename))
    db.execute("INSERT INTO notifications(ts,kind,message) VALUES (?,?,?)",
               (db.now(), "publish", f"Published to sample portal: {filename}"))
    return {"published": filename}


@router.post("/demo/reset")
async def demo_reset(request: Request):
    require_admin(request)

    import sys
    from pathlib import Path

    # Wipe DB
    if DB_PATH.exists():
        DB_PATH.unlink()
    db.init()

    # Clear dirs
    for directory in [ARCHIVE_DIR, PORTAL_PUB]:
        for f in directory.glob("*"):
            if f.is_file():
                f.unlink()

    # Copy seed PDFs
    pdfs = list(PDFS_SEED.glob("*.pdf"))
    for pdf in pdfs:
        shutil.copy2(pdf, PORTAL_PUB / pdf.name)

    # Re-ingest
    _BACKEND = Path(__file__).resolve().parents[2]
    sys.path.insert(0, str(_BACKEND))
    from scripts.seed import ingest_pdf  # noqa: PLC0415
    from .index import INDEX  # noqa: PLC0415

    for pdf in sorted(pdfs):
        await ingest_pdf(pdf, force=False)
    await INDEX.build_async()

    db.execute("INSERT INTO audit_log(ts,actor,action,detail) VALUES (?,?,?,?)",
               (db.now(), _actor(request), "demo_reset", f"{len(pdfs)} PDFs re-seeded"))
    return {"ok": True, "seeded": len(pdfs)}


# ---------------------------------------------------------------------------
# Documents
# ---------------------------------------------------------------------------

@router.get("/documents")
def documents(request: Request, status: str = "", doc_type: str = "",
              search: str = "", limit: int = 100):
    require_admin(request)
    sql = "SELECT * FROM documents WHERE 1=1"
    args: list = []
    if status:
        sql += " AND status=?"; args.append(status)
    if doc_type:
        sql += " AND doc_type=?"; args.append(doc_type)
    if search:
        sql += " AND (gr_number LIKE ? OR title LIKE ?)"; args += [f"%{search}%", f"%{search}%"]
    sql += " ORDER BY detected_at DESC LIMIT ?"
    args.append(limit)
    return [dict(r) for r in db.fetchall(sql, args)]


@router.get("/documents/{doc_id}")
def document_detail(doc_id: int, request: Request):
    require_admin(request)
    doc = db.fetchone("SELECT * FROM documents WHERE id=?", (doc_id,))
    if not doc:
        raise HTTPException(404, "Document not found")
    rules = db.fetchall("SELECT * FROM rules WHERE document_id=? ORDER BY page_no", (doc_id,))
    refs = db.fetchall("SELECT * FROM refs WHERE document_id=?", (doc_id,))
    pages = db.fetchall(
        "SELECT page_no, LENGTH(text) as chars FROM pages WHERE document_id=? ORDER BY page_no",
        (doc_id,))
    return {
        **dict(doc),
        "rules": [dict(r) for r in rules],
        "refs":  [dict(r) for r in refs],
        "pages": [dict(p) for p in pages],
    }


# ---------------------------------------------------------------------------
# Rules
# ---------------------------------------------------------------------------

@router.get("/rules")
def rules_current(request: Request):
    require_admin(request)
    rows = current_rules(SCHEME)
    return [dict(r) for r in rows]


@router.get("/rules/history")
def rules_history(request: Request, field: str = ""):
    require_admin(request)
    fields = [field] if field else all_fields(SCHEME)
    result = {}
    for f in fields:
        result[f] = [dict(r) for r in rule_history(SCHEME, f)]
    return result


@router.patch("/rules/{rule_id}")
async def edit_rule(rule_id: int, request: Request):
    require_admin(request)
    body = await request.json()
    allowed = {"value", "unit", "condition_text", "source_quote", "effective_from"}
    updates = {k: v for k, v in body.items() if k in allowed}
    if not updates:
        raise HTTPException(400, "Nothing to update")
    for col, val in updates.items():
        db.execute(f"UPDATE rules SET {col}=? WHERE id=?", (val, rule_id))
    db.execute("INSERT INTO audit_log(ts,actor,action,detail) VALUES (?,?,?,?)",
               (db.now(), _actor(request), "edit_rule", f"rule {rule_id}: {list(updates.keys())}"))
    return {"ok": True}


# ---------------------------------------------------------------------------
# Review queue
# ---------------------------------------------------------------------------

@router.get("/review")
def review_list(request: Request):
    require_admin(request)
    rows = db.fetchall(
        """SELECT rq.*, d.gr_number, d.gr_date, d.title, d.doc_type, d.confidence,
                  d.summary_en, d.file_path
           FROM review_queue rq JOIN documents d ON d.id=rq.document_id
           WHERE rq.status='pending'
           ORDER BY rq.id DESC""")
    result = []
    for row in rows:
        d = dict(row)
        rules = db.fetchall(
            "SELECT * FROM rules WHERE document_id=? ORDER BY page_no", (d["document_id"],))
        d["rules"] = [dict(r) for r in rules]
        result.append(d)
    return result


@router.post("/review/{review_id}/approve")
async def review_approve(review_id: int, request: Request):
    require_admin(request)
    rq = db.fetchone("SELECT * FROM review_queue WHERE id=?", (review_id,))
    if not rq or rq["status"] != "pending":
        raise HTTPException(404, "Review item not found or already decided")
    actor = _actor(request)
    db.execute(
        "UPDATE review_queue SET status='approved', decided_by=?, decided_at=? WHERE id=?",
        (actor, db.now(), review_id))
    await finalize(rq["run_id"], rq["document_id"], actor=actor)
    return {"ok": True}


@router.post("/review/{review_id}/reject")
async def review_reject(review_id: int, request: Request):
    require_admin(request)
    body = await request.json()
    note = body.get("note", "")
    rq = db.fetchone("SELECT * FROM review_queue WHERE id=?", (review_id,))
    if not rq or rq["status"] != "pending":
        raise HTTPException(404, "Review item not found or already decided")
    actor = _actor(request)
    db.execute(
        "UPDATE review_queue SET status='rejected', decided_by=?, decided_at=? WHERE id=?",
        (actor, db.now(), review_id))
    db.execute("UPDATE documents SET status='rejected' WHERE id=?", (rq["document_id"],))
    db.execute("UPDATE rules SET status='rejected' WHERE document_id=?", (rq["document_id"],))
    db.execute("INSERT INTO audit_log(ts,actor,action,detail) VALUES (?,?,?,?)",
               (db.now(), actor, "reject", f"document {rq['document_id']}: {note}"))
    return {"ok": True}


# ---------------------------------------------------------------------------
# Notifications
# ---------------------------------------------------------------------------

@router.get("/notifications")
def notifications(request: Request, unread_only: bool = False):
    require_admin(request)
    sql = "SELECT * FROM notifications"
    if unread_only:
        sql += " WHERE read=0"
    sql += " ORDER BY ts DESC LIMIT 50"
    return [dict(r) for r in db.fetchall(sql)]


@router.post("/notifications/read")
async def mark_read(request: Request):
    require_admin(request)
    body = await request.json()
    ids = body.get("ids", [])
    if ids:
        placeholders = ",".join("?" * len(ids))
        db.execute(f"UPDATE notifications SET read=1 WHERE id IN ({placeholders})", ids)
    else:
        db.execute("UPDATE notifications SET read=1")
    return {"ok": True}


# ---------------------------------------------------------------------------
# Questions log
# ---------------------------------------------------------------------------

@router.get("/questions")
def questions_log(request: Request, tab: str = "all", limit: int = 100):
    require_admin(request)
    sql = "SELECT * FROM queries WHERE 1=1"
    args: list = []
    if tab == "refused":
        sql += " AND refused=1"
    elif tab == "low_confidence":
        sql += " AND confidence < 0.5"
    elif tab == "thumbs_down":
        sql += " AND feedback=-1"
    sql += " ORDER BY ts DESC LIMIT ?"
    args.append(limit)
    rows = db.fetchall(sql, args)
    result = []
    for r in rows:
        d = dict(r)
        try:
            d["cited"] = json.loads(d["cited"] or "[]")
        except Exception:
            d["cited"] = []
        result.append(d)
    return result


# ---------------------------------------------------------------------------
# Evaluation
# ---------------------------------------------------------------------------

@router.post("/eval/run")
async def eval_run(request: Request, background_tasks: BackgroundTasks):
    require_admin(request)
    run_id_box: list[int] = []

    async def _bg():
        rid = await run_eval()
        run_id_box.append(rid)

    background_tasks.add_task(_bg)
    return {"started": True}


@router.get("/eval/latest")
def eval_latest(request: Request):
    require_admin(request)
    run = db.fetchone("SELECT * FROM eval_runs ORDER BY ts DESC LIMIT 1")
    if not run:
        return {"run": None, "results": []}
    results = db.fetchall(
        "SELECT * FROM eval_results WHERE run_id=? ORDER BY id", (run["id"],))
    return {"run": dict(run), "results": [dict(r) for r in results]}


@router.get("/eval/runs")
def eval_runs(request: Request):
    require_admin(request)
    return [dict(r) for r in db.fetchall("SELECT * FROM eval_runs ORDER BY ts DESC LIMIT 20")]


# ---------------------------------------------------------------------------
# Audit log
# ---------------------------------------------------------------------------

@router.get("/audit")
def audit(request: Request, actor: str = "", action: str = "", limit: int = 200):
    require_admin(request)
    sql = "SELECT * FROM audit_log WHERE 1=1"
    args: list = []
    if actor:
        sql += " AND actor=?"; args.append(actor)
    if action:
        sql += " AND action=?"; args.append(action)
    sql += " ORDER BY ts DESC LIMIT ?"
    args.append(limit)
    return [dict(r) for r in db.fetchall(sql, args)]


# ---------------------------------------------------------------------------
# Guardrails
# ---------------------------------------------------------------------------

@router.get("/guardrails")
def guardrails_status(request: Request):
    require_admin(request)
    from .guardrails import kill_switch_active, blocked_outbound_count
    from .config import OFFLINE_MODE
    today = datetime.now(timezone.utc).date().isoformat()
    pii_masks = db.fetchone(
        "SELECT COUNT(*) AS n FROM queries WHERE ts>=? AND question_masked LIKE '%[%'",
        (today,))["n"]
    personal_refusals = db.fetchone(
        "SELECT COUNT(*) AS n FROM queries WHERE ts>=? AND refused=1", (today,))["n"]
    return {
        "kill_switch": kill_switch_active(),
        "pii_masking": True,
        "pii_masks_today": pii_masks,
        "personal_status_refusals_today": personal_refusals,
        "cite_or_refuse": True,
        "human_review_amendments": True,
        "sources_allowlisted": True,
        "offline_mode": OFFLINE_MODE,
        "blocked_outbound_attempts": blocked_outbound_count(),
    }


@router.post("/guardrails/kill-switch")
async def set_kill(request: Request):
    require_admin(request)
    body = await request.json()
    state = bool(body.get("active", False))
    set_kill_switch(state)
    db.execute("INSERT INTO audit_log(ts,actor,action,detail) VALUES (?,?,?,?)",
               (db.now(), _actor(request), "kill_switch", str(state)))
    return {"kill_switch": state}


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------

@router.get("/settings")
def settings(request: Request):
    require_admin(request)
    from .config import OLLAMA_MODEL, EMBED_MODEL
    total_queries = db.fetchone("SELECT COUNT(*) AS n FROM queries")["n"]
    return {
        "llm_model": OLLAMA_MODEL,
        "embed_model": EMBED_MODEL,
        "total_queries": total_queries,
        "demo_users": ["citizen", "admin"],
    }


# ---------------------------------------------------------------------------
# System / LLM status  (GET /api/admin/system/llm)
# ---------------------------------------------------------------------------

@router.get("/system/llm")
async def system_llm(request: Request):
    """
    Returns live status of the local Ollama model.
    Polled every 5 s by the admin UI and citizen footer.
    No auth required — used by the status chip before login too.
    """
    from .llm import (
        OLLAMA_HOST, OLLAMA_MODEL, OLLAMA_NUM_CTX,
        get_stats, queue_length, ps_status,
    )
    from .config import OFFLINE_MODE

    stats = get_stats()
    ps    = await ps_status()

    loaded    = bool(ps)
    size_b    = ps.get("size",      0)
    size_vram = ps.get("size_vram", 0)
    expires   = ps.get("expires_at", "")
    # keep_alive -1 makes Ollama set expires_at to a far-future date or "0001-01-01T00:00:00Z"
    always_on = (expires.startswith("0001") or expires == "") and loaded

    return {
        "backend":           "ollama",
        "model":             OLLAMA_MODEL,
        "loaded":            loaded,
        "size":              size_b,
        "size_vram":         size_vram,
        "expires_at":        "always" if always_on else expires,
        "keep_alive":        -1,
        "num_ctx":           OLLAMA_NUM_CTX,
        "last_latency_ms":   stats.last_latency_ms,
        "last_tokens_per_sec": stats.last_tokens_per_sec,
        "last_load_duration_ms": stats.last_load_duration_ms,
        "queue_length":      queue_length(),
        "offline_mode":      OFFLINE_MODE,
        "load_time_s":       round(stats.load_time_s, 1),
    }


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _actor(request: Request) -> str:
    from .auth import get_current_user
    user = get_current_user(request)
    return user["username"] if user else "unknown"
