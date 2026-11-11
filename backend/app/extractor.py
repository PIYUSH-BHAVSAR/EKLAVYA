"""LLM-based extraction of structured data from GR page text.

Adapted for gemma4:e2b-it-qat (4.6 B Q4_0):
- Text budget: at most ~4 000 chars per call (header page + operative paragraphs).
- OCR junk stripped (lines with fewer than 3 word-characters dropped).
- Uses Ollama structured outputs (format = JSON Schema) for determinism.
- Split into two calls when the document is long:
    Call 1 — metadata: gr_number / gr_date / title / department / scheme /
              doc_type / summary_mr / summary_en / refers_to
    Call 2 — rules array
- Disk cache keyed on content so re-seeding costs zero LLM calls.
"""
from __future__ import annotations

import logging
import re
from typing import Literal, Optional

from pydantic import BaseModel, field_validator

from .llm import complete

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Allowed field names for rules
# ---------------------------------------------------------------------------

FIELDS = [
    "age_min",
    "age_max",
    "income_limit",
    "benefit_amount",
    "payment_frequency",
    "ekyc_required",
    "ekyc_deadline",
    "application_deadline",
    "documents_required",
    "exclusion",
    "eligible_category",
    "verification_method",
    "other",
]


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class Rule(BaseModel):
    field: str
    value: str
    unit: Optional[str] = None
    condition_text: str
    source_quote: str           # verbatim text copied from the page, max 200 chars
    page_no: int
    effective_from: Optional[str] = None
    grounded: Optional[bool] = None   # set by verifier, not the LLM

    @field_validator("field")
    @classmethod
    def _valid_field(cls, v: str) -> str:
        return v if v in FIELDS else "other"

    @field_validator("source_quote")
    @classmethod
    def _truncate_quote(cls, v: str) -> str:
        return (v or "")[:200]


class Ref(BaseModel):
    gr_number: Optional[str] = None
    gr_date: Optional[str] = None
    relation: Literal["replaces", "amends", "extends", "clarifies", "refers"] = "refers"


class Extraction(BaseModel):
    gr_number: str
    gr_date: str                # ISO YYYY-MM-DD
    title: str
    department: str
    scheme: str
    doc_type: Literal["new", "amendment", "extension", "clarification", "other"]
    summary_mr: str
    summary_en: str
    rules: list[Rule]
    refers_to: list[Ref] = []


# ---------------------------------------------------------------------------
# JSON Schemas for Ollama structured outputs
# (Ollama passes these as `format` — must be a flat/resolved JSON Schema dict)
# ---------------------------------------------------------------------------

_REF_SCHEMA = {
    "type": "object",
    "properties": {
        "gr_number": {"type": ["string", "null"]},
        "gr_date":   {"type": ["string", "null"]},
        "relation":  {"type": "string", "enum": ["replaces","amends","extends","clarifies","refers"]},
    },
    "required": ["relation"],
    "additionalProperties": False,
}

_RULE_SCHEMA = {
    "type": "object",
    "properties": {
        "field":          {"type": "string", "enum": FIELDS},
        "value":          {"type": "string"},
        "unit":           {"type": ["string", "null"]},
        "condition_text": {"type": "string"},
        "source_quote":   {"type": "string"},
        "page_no":        {"type": "integer"},
        "effective_from": {"type": ["string", "null"]},
    },
    "required": ["field", "value", "condition_text", "source_quote", "page_no"],
    "additionalProperties": False,
}

_META_SCHEMA = {
    "type": "object",
    "properties": {
        "gr_number":   {"type": "string"},
        "gr_date":     {"type": "string"},
        "title":       {"type": "string"},
        "department":  {"type": "string"},
        "scheme":      {"type": "string"},
        "doc_type":    {"type": "string", "enum": ["new","amendment","extension","clarification","other"]},
        "summary_mr":  {"type": "string"},
        "summary_en":  {"type": "string"},
        "refers_to":   {"type": "array", "items": _REF_SCHEMA},
    },
    "required": ["gr_number","gr_date","title","department","scheme","doc_type","summary_mr","summary_en"],
    "additionalProperties": False,
}

_RULES_SCHEMA = {
    "type": "object",
    "properties": {
        "rules": {"type": "array", "items": _RULE_SCHEMA},
    },
    "required": ["rules"],
    "additionalProperties": False,
}


# ---------------------------------------------------------------------------
# System prompts (kept short for a 4B model)
# ---------------------------------------------------------------------------

_META_SYSTEM = """You extract header information from Government of Maharashtra GR documents.
Return ONLY a JSON object with these keys:
  gr_number  – reference number as printed
  gr_date    – ISO YYYY-MM-DD
  title      – short title (max 15 words)
  department – issuing department name
  scheme     – scheme name as written
  doc_type   – one of: new | amendment | extension | clarification | other
  summary_mr – 1-sentence summary in Marathi (max 30 words)
  summary_en – 1-sentence summary in English (max 30 words)
  refers_to  – array of {gr_number, gr_date, relation} for referenced GRs (empty array if none)

STRICT: Never invent numbers or dates not present in the text.
Output ONLY the JSON object, no markdown, no commentary, no trailing text."""

_RULES_SYSTEM = f"""You extract eligibility rules from Government of Maharashtra GR documents.
Return ONLY a JSON object with a single key "rules" whose value is an array.
Each rule has:
  field          – one of: {", ".join(FIELDS)}
  value          – the rule value (string, no units)
  unit           – unit if any, e.g. "years", "lakh rupees", or null
  condition_text – when/who this rule applies to
  source_quote   – VERBATIM text copied from the page (max 200 chars, REQUIRED)
  page_no        – page number (integer)
  effective_from – ISO date if stated, else null

STRICT:
- source_quote MUST be copied verbatim from the supplied page text.
- Never invent numbers, dates, or facts not in the text.
- If no rules are found, return {{"rules": []}}
Output ONLY the JSON object, no markdown, no commentary."""


# ---------------------------------------------------------------------------
# Text cleaning
# ---------------------------------------------------------------------------

_OCR_JUNK_RE = re.compile(r"^.{0,2}$|^[\W\d\s]{1,5}$")


def _clean_line(line: str) -> bool:
    """True if the line is worth keeping (has ≥3 word characters)."""
    return len(re.findall(r"\w", line)) >= 3


def trim_pages(pages: list[tuple[int, str]], max_chars: int = 4000) -> str:
    """
    Clean OCR junk and cap total text at max_chars.
    Drops lines with < 3 word-characters (OCR noise).
    """
    clean = []
    for n, t in pages:
        lines = [l.strip() for l in t.splitlines() if _clean_line(l)]
        clean.append((n, "\n".join(lines)))

    # Distribute budget evenly but give the first page (header) more space
    if not clean:
        return ""
    per = max(1000, max_chars // max(1, len(clean)))
    first_budget = min(len(clean[0][1]), max_chars // 2)
    parts = [f"[[PAGE {clean[0][0]}]]\n{clean[0][1][:first_budget]}"]
    remaining = max_chars - first_budget
    for n, t in clean[1:]:
        parts.append(f"[[PAGE {n}]]\n{t[:per]}")
    return "\n".join(parts)[:max_chars]


# ---------------------------------------------------------------------------
# Main extraction function (two-call strategy)
# ---------------------------------------------------------------------------

async def extract(pages: list[tuple[int, str]]) -> Extraction:
    """Extract structured data from a list of (page_no, text) tuples.

    Uses two LLM calls:
      1. Metadata (header fields + references) — header page only
      2. Rules — operative pages

    Both calls are disk-cached so re-seeding costs zero LLM calls.
    """
    if not pages:
        raise ValueError("No pages provided to extractor")

    # --- Call 1: metadata from header pages (first 1-2 pages) ---------------
    header_pages = pages[:2]
    header_body  = trim_pages(header_pages, max_chars=3000)

    log.debug("[extractor] call 1 – metadata, body=%d chars", len(header_body))
    meta_data = await complete(
        _META_SYSTEM,
        header_body,
        schema=_META_SCHEMA,
        max_tokens=2500,   # raised: Marathi summaries can be 300-400 chars each
        use_cache=True,
    )

    # --- Call 2: rules from operative paragraphs (all pages) -----------------
    rules_body = trim_pages(pages, max_chars=4000)

    log.debug("[extractor] call 2 – rules, body=%d chars", len(rules_body))
    rules_data = await complete(
        _RULES_SYSTEM,
        rules_body,
        schema=_RULES_SCHEMA,
        max_tokens=2000,
        use_cache=True,
    )

    # --- Merge and validate ---------------------------------------------------
    merged = {
        **meta_data,
        "rules":     rules_data.get("rules", []),
        "refers_to": meta_data.get("refers_to", []),
    }

    return Extraction.model_validate(merged)
