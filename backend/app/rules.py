"""Current-rule computation and rule history.

A rule is "current" when:
  - It is the approved rule with the latest effective date (or GR date as fallback)
    for a given (scheme, field) pair.
  - Its parent document has status = 'live'.

A rule is "superseded" when a later approved rule covers the same (scheme, field).
"""
from __future__ import annotations

import sqlite3

from . import db


def current_rules(scheme: str) -> list[sqlite3.Row]:
    """Return the single most-recent approved rule for each (scheme, field)."""
    rows = db.fetchall(
        """
        SELECT r.*, d.gr_number, d.gr_date, d.id AS doc_id
        FROM   rules r
        JOIN   documents d ON d.id = r.document_id
        WHERE  r.scheme = ?
          AND  r.status = 'approved'
          AND  d.status = 'live'
        """,
        (scheme,),
    )

    best: dict[str, tuple[str, sqlite3.Row]] = {}
    for row in rows:
        key = row["field"]
        # Use effective_from if set, otherwise fall back to gr_date, else empty string
        stamp: str = row["effective_from"] or row["gr_date"] or ""
        if key not in best or stamp >= best[key][0]:
            best[key] = (stamp, row)

    return [v[1] for v in best.values()]


def history(scheme: str, field: str) -> list[sqlite3.Row]:
    """Return all approved rules for (scheme, field) in chronological order.

    Each row includes the GR number and date for display in the timeline.
    """
    return db.fetchall(
        """
        SELECT r.*, d.gr_number, d.gr_date
        FROM   rules r
        JOIN   documents d ON d.id = r.document_id
        WHERE  r.scheme = ?
          AND  r.field  = ?
          AND  r.status = 'approved'
          AND  d.status = 'live'
        ORDER BY COALESCE(r.effective_from, d.gr_date) ASC
        """,
        (scheme, field),
    )


def all_fields(scheme: str) -> list[str]:
    """Return the distinct fields that have at least one approved rule for the scheme."""
    rows = db.fetchall(
        """
        SELECT DISTINCT r.field
        FROM   rules r
        JOIN   documents d ON d.id = r.document_id
        WHERE  r.scheme = ?
          AND  r.status = 'approved'
          AND  d.status = 'live'
        ORDER BY r.field
        """,
        (scheme,),
    )
    return [r["field"] for r in rows]


def rules_for_document(doc_id: int) -> list[sqlite3.Row]:
    """Return all rules for a specific document (any status)."""
    return db.fetchall(
        "SELECT * FROM rules WHERE document_id = ? ORDER BY page_no, id",
        (doc_id,),
    )
