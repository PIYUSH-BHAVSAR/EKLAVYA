"""Public API routes (no auth required for login; citizen routes need a token)."""
from __future__ import annotations

import json

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request
from pydantic import BaseModel

from . import db
from .answer import ask
from .auth import login, logout, require_auth
from .config import SCHEME
from .index import INDEX

router = APIRouter()


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

class LoginBody(BaseModel):
    username: str
    password: str


@router.post("/login")
def do_login(body: LoginBody):
    return login(body.username, body.password)


@router.post("/logout")
def do_logout(request: Request):
    from .auth import _get_token
    token = _get_token(request)
    if token:
        logout(token)
    return {"ok": True}


@router.get("/me")
def me(request: Request):
    user = require_auth(request)
    return {"username": user["username"], "role": user["role"]}


# ---------------------------------------------------------------------------
# Schemes / starter questions
# ---------------------------------------------------------------------------

STARTER_QUESTIONS = [
    {"en": "Who is eligible for loans from this corporation?",
     "mr": "या महामंडळाच्या कर्जासाठी कोण पात्र आहे?"},
    {"en": "What is the maximum loan amount available?",
     "mr": "जास्तीत जास्त किती कर्ज मिळू शकते?"},
    {"en": "What is the interest rate on loans?",
     "mr": "कर्जावरील व्याजदर किती आहे?"},
    {"en": "What documents are required to apply?",
     "mr": "अर्जासाठी कोणते कागदपत्रे लागतात?"},
    {"en": "What is the repayment period for loans?",
     "mr": "कर्जाची परतफेड किती वर्षांत करायची आहे?"},
    {"en": "Which tribes or communities are covered?",
     "mr": "या योजनेत कोणत्या जमाती किंवा समुदायांचा समावेश आहे?"},
]


@router.get("/schemes")
def schemes(request: Request):
    require_auth(request)
    return [
        {
            "id": "shabari",
            "name": SCHEME,
            "name_mr": "शबरी आदिवासी वित्त व विकास महामंडळ",
            "department": "शबरी आदिवासी वित्त व विकास महामंडळ (Shabari Adivasi Finance & Development Corporation)",
            "starter_questions": STARTER_QUESTIONS,
        }
    ]


@router.get("/system/llm")
async def system_llm_public():
    """
    Public mirror of /api/admin/system/llm — no auth needed so the
    status chip works on the login page and citizen view.
    """
    from .routes_admin import system_llm
    from fastapi import Request as _Req
    # Re-use the admin handler but bypass auth
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
# Chat
# ---------------------------------------------------------------------------

class ChatBody(BaseModel):
    question: str
    lang: str = "auto"


@router.post("/chat")
async def chat(body: ChatBody, request: Request):
    user = require_auth(request)
    result = await ask(body.question, username=user["username"])
    return result


class FeedbackBody(BaseModel):
    vote: int   # 1 or -1


@router.post("/chat/{query_id}/feedback")
def feedback(query_id: int, body: FeedbackBody, request: Request):
    require_auth(request)
    if body.vote not in (1, -1):
        raise HTTPException(400, "vote must be 1 or -1")
    db.execute("UPDATE queries SET feedback = ? WHERE id = ?", (body.vote, query_id))
    return {"ok": True}


# ---------------------------------------------------------------------------
# Query history (citizen sees own; admin sees all via admin routes)
# ---------------------------------------------------------------------------

@router.get("/history")
def history(request: Request, limit: int = 50):
    user = require_auth(request)
    rows = db.fetchall(
        """SELECT id, ts, question_masked, answer, cited, refused, confidence,
                  latency_ms, feedback
           FROM queries WHERE username = ?
           ORDER BY ts DESC LIMIT ?""",
        (user["username"], limit),
    )
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
# Source viewer (page text + cited quote)
# ---------------------------------------------------------------------------

@router.get("/sources/{doc_id}/page/{page_no}")
def source_page(doc_id: int, page_no: int, request: Request, quote: str = ""):
    require_auth(request)
    page = db.fetchone(
        "SELECT text FROM pages WHERE document_id = ? AND page_no = ?",
        (doc_id, page_no),
    )
    if not page:
        raise HTTPException(404, "Page not found")

    from .textutil import highlight_quote
    text = page["text"]
    highlighted = highlight_quote(text, quote) if quote else text

    doc = db.fetchone(
        "SELECT gr_number, gr_date, title, file_path FROM documents WHERE id = ?",
        (doc_id,),
    )
    return {
        "doc_id":     doc_id,
        "page_no":    page_no,
        "text":       text,
        "highlighted": highlighted,
        "gr_number":  doc["gr_number"] if doc else None,
        "gr_date":    doc["gr_date"]   if doc else None,
        "title":      doc["title"]     if doc else None,
        "file_path":  doc["file_path"] if doc else None,
    }
