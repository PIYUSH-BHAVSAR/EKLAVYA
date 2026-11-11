"""Input/output guardrails:
  - PII masking (Aadhaar, phone, long numbers)
  - Personal-status question detection → automatic refusal
  - Kill switch (set by admin; disables /chat endpoint)
  - Offline HTTP guard (blocks outbound calls to non-localhost hosts when OFFLINE_MODE=1)

All matching uses simple substring / regex so it runs at near-zero latency.
"""
from __future__ import annotations

import logging
import os
import re
from urllib.parse import urlparse

import regex

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Offline mode — outbound HTTP guard
# ---------------------------------------------------------------------------

_OFFLINE_MODE: bool = os.getenv("OFFLINE_MODE", "1") not in ("0", "false", "False")
_BLOCKED_ATTEMPTS: int = 0

_LOCAL_HOSTS = frozenset({"localhost", "127.0.0.1", "::1"})


def blocked_outbound_count() -> int:
    """Return how many outbound calls have been blocked since startup."""
    return _BLOCKED_ATTEMPTS


def check_offline_url(url: str) -> None:
    """
    Raise RuntimeError if OFFLINE_MODE is on and the URL points outside localhost.
    Call this before any httpx / requests call in application code.
    """
    global _BLOCKED_ATTEMPTS
    if not _OFFLINE_MODE:
        return
    try:
        host = urlparse(url).hostname or ""
    except Exception:
        host = ""
    if host not in _LOCAL_HOSTS:
        _BLOCKED_ATTEMPTS += 1
        log.error(
            "[offline-guard] BLOCKED outbound request to %s (total blocked: %d)",
            url, _BLOCKED_ATTEMPTS,
        )
        raise RuntimeError(
            f"OFFLINE_MODE=1: outbound request to '{url}' is not allowed. "
            "Only localhost/127.0.0.1 may be reached."
        )

# ---------------------------------------------------------------------------
# PII patterns
# ---------------------------------------------------------------------------

_PII_PATTERNS: list[tuple[regex.Pattern, str]] = [
    (regex.compile(r"\b\d{4}\s?\d{4}\s?\d{4}\b"),  "[AADHAAR]"),
    (regex.compile(r"\b[6-9]\d{9}\b"),              "[PHONE]"),
    (regex.compile(r"\b\d{9,18}\b"),                "[NUMBER]"),
]


def mask_pii(text: str) -> str:
    """Replace PII patterns with placeholder tokens."""
    for pattern, replacement in _PII_PATTERNS:
        text = pattern.sub(replacement, text)
    return text


# ---------------------------------------------------------------------------
# Personal-status question detection
# ---------------------------------------------------------------------------

_PERSONAL_TRIGGERS: list[str] = [
    # English
    "my application", "my status", "my loan", "my account",
    "my payment", "loan approved", "did i get", "have i received",
    "am i eligible", "check my", "my installment", "my disbursement",
    # Marathi
    "माझा अर्ज", "माझे कर्ज", "माझं स्टेटस", "माझे स्टेटस",
    "कर्ज मिळाले का", "माझ्या खात्यात", "माझा लाभ", "माझी पात्रता",
    "मी पात्र आहे का", "हप्ता आला नाही", "पैसे आले नाहीत",
]

REFUSE_PERSONAL = (
    "I can explain the published rules of this scheme, but I cannot check your personal "
    "application or loan status — I do not have access to that information. "
    "Please visit the Shabari Mahamandal office in Nashik or contact your district tribal office."
)

REFUSE_PERSONAL_MR = (
    "मी या योजनेचे प्रकाशित नियम सांगू शकतो, परंतु तुमचा अर्ज किंवा कर्ज स्थिती तपासू शकत नाही. "
    "कृपया नाशिकमधील शबरी महामंडळाच्या कार्यालयात किंवा जिल्हा आदिवासी कार्यालयाशी संपर्क साधा."
)


def is_personal_status(question: str) -> bool:
    """Return True if the question is asking about the user's own case."""
    ql = question.lower()
    return any(trigger in ql for trigger in _PERSONAL_TRIGGERS)


def personal_refuse_message(question: str) -> str:
    """Return the refusal message in the appropriate language."""
    # Simple heuristic: if the question contains Devanagari, reply in Marathi
    if any("\u0900" <= c <= "\u097F" for c in question):
        return REFUSE_PERSONAL_MR
    return REFUSE_PERSONAL


# ---------------------------------------------------------------------------
# Out-of-scope detection (very light — main gating is done by the LLM)
# ---------------------------------------------------------------------------

_OUT_OF_SCOPE_TRIGGERS: list[str] = [
    "weather", "cricket", "movie", "stock", "share price",
    "recipe", "joke", "election result",
]


def is_out_of_scope(question: str) -> bool:
    ql = question.lower()
    return any(trigger in ql for trigger in _OUT_OF_SCOPE_TRIGGERS)


REFUSE_OUT_OF_SCOPE = (
    "I can only answer questions about published Government of Maharashtra orders and schemes. "
    "This question is outside that scope."
)


# ---------------------------------------------------------------------------
# Kill switch (in-process flag; persists only for the lifetime of the server)
# ---------------------------------------------------------------------------

_KILL_SWITCH: bool = False


def kill_switch_active() -> bool:
    return _KILL_SWITCH


def set_kill_switch(state: bool) -> None:
    global _KILL_SWITCH
    _KILL_SWITCH = state


KILL_SWITCH_MESSAGE = (
    "The citizen assistant is temporarily unavailable for maintenance. "
    "Please try again shortly."
)
