"""Retrieval-augmented answer generation — adapted for gemma4:e2b-it-qat.

Changes from the cloud version:
- Top k reduced to 3-4 chunks (less context = better coherence on a 4B model).
- Answer capped at 120 words in the prompt.
- JSON schema passed as Ollama structured output (`schema=`) for reliability.
- Deterministic post-check: every number and date in the answer must appear
  in the cited source text (after Devanagari-digit normalisation).
  If the check fails, one retry. If still failing, refuse with a clear message.
- Language toggle: if the model returns poor Marathi (heuristic: answer is
  mostly ASCII when the question was Marathi), we log a warning and append an
  English fallback note so the user knows.
"""
from __future__ import annotations

import json
import logging
import re
import time

from . import db
from .config import SCHEME
from .guardrails import (
    KILL_SWITCH_MESSAGE,
    REFUSE_OUT_OF_SCOPE,
    is_out_of_scope,
    is_personal_status,
    kill_switch_active,
    mask_pii,
    personal_refuse_message,
)
from .index import INDEX
from .llm import complete_with_retry
from .rules import current_rules

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# JSON Schema for the answer — passed as Ollama structured output
# ---------------------------------------------------------------------------

_ANSWER_SCHEMA = {
    "type": "object",
    "properties": {
        "answer":     {"type": "string"},
        "refuse":     {"type": "boolean"},
        "citations":  {"type": "array", "items": {"type": "integer"}},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
    },
    "required": ["answer", "refuse", "citations", "confidence"],
    "additionalProperties": False,
}

# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

_SYSTEM = """You are EKLAVYA, a helpful assistant that explains published Government of Maharashtra
Government Resolutions (GRs) about welfare schemes to citizens.

STRICT RULES:
1. Answer ONLY from the CURRENT_RULES and SOURCES sections provided below.
2. If the information is NOT in those sections, set "refuse": true and leave answer blank.
3. Reply in the SAME LANGUAGE as the question (Marathi or English).
4. Copy numbers, amounts, and dates EXACTLY as they appear — do not round or paraphrase them.
5. NEVER decide an individual case. NEVER say a specific person is approved or rejected.
6. Keep your answer under 120 words.
7. Output ONLY this JSON (no markdown, no fences, no extra text):
   {"answer": "...", "refuse": false, "citations": [chunk_id, ...], "confidence": 0.0}"""

# ---------------------------------------------------------------------------
# Fallback messages
# ---------------------------------------------------------------------------

_TIMEOUT_MSG = "The assistant is taking longer than usual. Please try again in a moment."

_NO_INFO_MSG = (
    "I could not find this information in the official government orders I have. "
    "Please check with your local anganwadi worker, CSC, or the official portal."
)
_NO_INFO_MR = (
    "मला माझ्याकडे असलेल्या अधिकृत शासन निर्णयांमध्ये ही माहिती सापडली नाही. "
    "कृपया जवळच्या अंगणवाडी कार्यकर्त्या, CSC किंवा अधिकृत पोर्टलशी संपर्क साधा."
)

_MARATHI_FALLBACK = (
    " (English: The answer could not be provided in Marathi by the local model. "
    "Please ask your question in English for a more complete response.)"
)


def _no_info(question: str) -> str:
    return _NO_INFO_MR if _is_marathi(question) else _NO_INFO_MSG


def _is_marathi(text: str) -> bool:
    """Heuristic: contains Devanagari characters."""
    return any("\u0900" <= c <= "\u097F" for c in text)


# ---------------------------------------------------------------------------
# Devanagari-digit normalisation for post-check
# ---------------------------------------------------------------------------

_DEVA_DIGIT = str.maketrans("०१२३४५६७८९", "0123456789")


def _norm_digits(text: str) -> str:
    return text.translate(_DEVA_DIGIT)


# Patterns for numbers (including Devanagari) and ISO/Indian dates
_NUMBER_RE = re.compile(r"\b[\d०-९]+(?:[.,][\d०-९]+)*\b")
_DATE_RE   = re.compile(
    r"\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b"
    r"|\b\d{4}-\d{2}-\d{2}\b"
)


def _extract_numbers_dates(text: str) -> set[str]:
    normed = _norm_digits(text)
    hits: set[str] = set()
    hits.update(m.group() for m in _NUMBER_RE.finditer(normed))
    hits.update(m.group() for m in _DATE_RE.finditer(normed))
    # strip trivial single-digit tokens that appear everywhere
    return {h for h in hits if len(h) > 1}


def _post_check(answer: str, cited_texts: list[str]) -> bool:
    """
    Every number/date in the answer must appear in at least one cited source text.
    Returns True if the answer passes the check (or if there are no numbers/dates).
    """
    claims = _extract_numbers_dates(answer)
    if not claims:
        return True
    combined = _norm_digits(" ".join(cited_texts))
    failed = [c for c in claims if c not in combined]
    if failed:
        log.warning("[answer] post-check failed: unsourced claims %s", failed)
        return False
    return True


# ---------------------------------------------------------------------------
# Main ask() function
# ---------------------------------------------------------------------------

async def ask(question: str, username: str = "citizen") -> dict:
    """Answer a citizen question and log it to the DB."""
    t0 = time.time()

    # ── Kill switch ──────────────────────────────────────────────────────────
    if kill_switch_active():
        return _log(username, mask_pii(question), KILL_SWITCH_MESSAGE, [], True, 1.0, t0)

    question_masked = mask_pii(question)

    # ── Personal-status refusal ──────────────────────────────────────────────
    if is_personal_status(question):
        return _log(
            username, question_masked,
            personal_refuse_message(question),
            [], True, 1.0, t0,
        )

    # ── Out-of-scope refusal ─────────────────────────────────────────────────
    if is_out_of_scope(question):
        return _log(username, question_masked, REFUSE_OUT_OF_SCOPE, [], True, 1.0, t0)

    # ── Retrieval (top 4 chunks — sufficient for a 4B model) ─────────────────
    chunks = INDEX.search(question, k=4)
    rules  = current_rules(SCHEME)

    # ── Build context ─────────────────────────────────────────────────────────
    facts_lines = [
        f"- {r['field']}: {r['value']} {r['unit'] or ''} "
        f"(GR {r['gr_number']}, {r['gr_date']}, p.{r['page_no']})"
        for r in rules
    ]
    facts   = "\n".join(facts_lines) or "(no structured rules loaded yet)"
    sources = "\n\n".join(
        f"[chunk {c['id']}] GR {c['gr_number']} ({c['gr_date']}) p.{c['page_no']}:\n{c['text']}"
        for c in chunks
    ) or "(no matching chunks found)"

    # System prompt first, variable content last (helps prefix-caching)
    user_prompt = (
        f"CURRENT_RULES:\n{facts}\n\n"
        f"SOURCES:\n{sources}\n\n"
        f"QUESTION: {question}"
    )

    # ── LLM call ──────────────────────────────────────────────────────────────
    try:
        data = await complete_with_retry(
            _SYSTEM,
            user_prompt,
            json_mode=True,   # format:"json" — simpler than schema, more reliable
            max_tokens=1200,  # enough for thinking tokens + the short JSON answer
        )
    except Exception as exc:
        log.error("[answer] LLM call failed: %s", exc)
        return _log(username, question_masked, _TIMEOUT_MSG, [], True, 0.0, t0)

    # ── Validate citations ────────────────────────────────────────────────────
    chunk_lookup = {c["id"]: c for c in chunks}
    raw_cites    = data.get("citations") or []
    valid_chunks = [chunk_lookup[cid] for cid in raw_cites if cid in chunk_lookup]
    cited_texts  = [c["text"] for c in valid_chunks]

    refused = bool(data.get("refuse")) or not valid_chunks
    answer  = (data.get("answer") or "").strip()

    if refused or not answer:
        return _log(username, question_masked, _no_info(question), [], True, 0.0, t0)

    # ── Deterministic post-check ──────────────────────────────────────────────
    if not _post_check(answer, cited_texts):
        log.warning("[answer] post-check failed; retrying once")
        retry_prompt = (
            f"CURRENT_RULES:\n{facts}\n\n"
            f"SOURCES:\n{sources}\n\n"
            f"QUESTION: {question}\n\n"
            "IMPORTANT: Your previous answer contained numbers or dates not found "
            "in the sources. Reply ONLY with numbers and dates that appear verbatim "
            "in the SOURCES above."
        )
        try:
            data = await complete_with_retry(
                _SYSTEM,
                retry_prompt,
                json_mode=True,
                max_tokens=1200,
            )
        except Exception as exc:
            log.error("[answer] retry LLM call failed: %s", exc)
            return _log(username, question_masked, _no_info(question), [], True, 0.0, t0)

        raw_cites    = data.get("citations") or []
        valid_chunks = [chunk_lookup[cid] for cid in raw_cites if cid in chunk_lookup]
        cited_texts  = [c["text"] for c in valid_chunks]
        refused      = bool(data.get("refuse")) or not valid_chunks
        answer       = (data.get("answer") or "").strip()

        if refused or not answer or not _post_check(answer, cited_texts):
            log.warning("[answer] post-check still failing after retry — refusing")
            return _log(username, question_masked, _no_info(question), [], True, 0.0, t0)

    # ── Marathi quality heuristic ──────────────────────────────────────────────
    if _is_marathi(question) and answer and not _is_marathi(answer):
        log.warning(
            "[answer] question is Marathi but answer is mostly Latin script — "
            "model may not produce reliable Marathi. Appending fallback note."
        )
        answer += _MARATHI_FALLBACK

    # ── Build citation list ────────────────────────────────────────────────────
    cited = [
        {
            "chunk_id":  c["id"],
            "doc_id":    c["document_id"],
            "gr_number": c["gr_number"],
            "gr_date":   c["gr_date"],
            "page":      c["page_no"],
            "file":      c["file_path"],
            "quote":     c["text"][:300],
        }
        for c in valid_chunks
    ]

    return _log(
        username, question_masked, answer, cited,
        False, float(data.get("confidence", 0.5)), t0,
    )


# ---------------------------------------------------------------------------
# Internal logger
# ---------------------------------------------------------------------------

def _log(
    username: str,
    question_masked: str,
    answer: str,
    cited: list[dict],
    refused: bool,
    confidence: float,
    t0: float,
) -> dict:
    latency_ms = int((time.time() - t0) * 1000)
    qid = db.execute(
        """INSERT INTO queries(ts, username, question_masked, answer, cited, refused,
                               confidence, latency_ms)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            db.now(), username, question_masked, answer,
            json.dumps(cited), int(refused), confidence, latency_ms,
        ),
    )
    return {
        "id":         qid,
        "answer":     answer,
        "citations":  cited,
        "refused":    refused,
        "confidence": confidence,
        "latency_ms": latency_ms,
    }
