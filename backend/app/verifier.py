"""Grounding verification: confirms each extracted rule's source_quote actually
appears in the page text, using fuzzy matching via rapidfuzz.

Also decides whether a document needs human review before going live.
"""
from __future__ import annotations

from rapidfuzz import fuzz

from .extractor import Extraction
from .textutil import norm


# ---------------------------------------------------------------------------
# Grounding check
# ---------------------------------------------------------------------------

def _quote_found(quote: str, page_text: str, all_text: str) -> bool:
    """Return True if the normalised quote is reasonably grounded in the document."""
    if not quote:
        return False
    nq = norm(quote)
    np = norm(page_text)
    na = norm(all_text)
    # Exact containment first (fast path)
    if nq in np or nq in na:
        return True
    # Fuzzy partial match ≥ 90 % on the full document
    return fuzz.partial_ratio(nq, na) >= 90


# ---------------------------------------------------------------------------
# Public interface
# ---------------------------------------------------------------------------

def verify(ext: Extraction, pages: list[tuple[int, str]]) -> tuple[float, list[str]]:
    """Ground each rule and decide if human review is needed.

    Modifies ext.rules in-place (sets rule.grounded).

    Returns:
        confidence – fraction of rules that are grounded (0.0 – 1.0)
        reasons    – list of reason strings; non-empty → send to review queue
    """
    # Build a per-page text lookup and a full-document blob
    page_text: dict[int, str] = {n: t for n, t in pages}
    all_text: str = " ".join(t for _, t in pages)

    bad = 0
    for rule in ext.rules:
        page = page_text.get(rule.page_no, "")
        ok = _quote_found(rule.source_quote, page, all_text)
        rule.grounded = ok
        if not ok:
            bad += 1

    total = max(1, len(ext.rules))
    confidence: float = 1.0 - bad / total

    # Collect reasons for review
    reasons: list[str] = []

    # Amendments always need a human eye
    if ext.doc_type in ("amendment", "extension", "clarification") or ext.refers_to:
        reasons.append("amendment: human review required")

    # Low grounding confidence
    if confidence < 0.9:
        reasons.append(f"low grounding ({confidence:.0%})")

    return confidence, reasons


# ---------------------------------------------------------------------------
# Helper used by the review API to re-verify a single edited rule
# ---------------------------------------------------------------------------

def verify_rule(source_quote: str, page_no: int, pages: list[tuple[int, str]]) -> bool:
    """Check a single quote after an admin edit."""
    page_text = {n: t for n, t in pages}
    all_text = " ".join(t for _, t in pages)
    return _quote_found(source_quote, page_text.get(page_no, ""), all_text)
