#!/usr/bin/env python3
"""Seed script: ingest all PDFs from data/pdfs_seed/ into the database.

Each PDF is processed through the full pipeline (read → chunk → extract →
verify) and immediately approved and set to 'live' — seed GRs are treated as
pre-verified.  Run this once after downloading the real GRs.

Usage:
    cd eklavya
    python -m scripts.seed [--force]

  --force  : delete existing records for a PDF if its sha256 already exists,
             then re-ingest. Useful after editing the prompt.
"""
from __future__ import annotations

import asyncio
import csv
import hashlib
import shutil
import sys
from pathlib import Path

# ── make sure 'backend' is on sys.path so `from app.xxx import` works ──
_BACKEND = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(_BACKEND))

from app import db  # noqa: E402  (side-effect: creates DB + tables)
from app.chunker import chunk_pages  # noqa: E402
from app.config import PDFS_SEED, PORTAL_PUB, SCHEME  # noqa: E402
from app.extractor import extract  # noqa: E402
from app.index import INDEX  # noqa: E402
from app.reader import read_pdf  # noqa: E402
from app.verifier import verify  # noqa: E402


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_manifest() -> dict[str, dict]:
    """Return {filename: row_dict} from data/manifest.csv if it exists."""
    csv_path = Path(__file__).resolve().parents[1] / "data" / "manifest.csv"
    if not csv_path.exists():
        return {}
    with csv_path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return {row["file"]: row for row in reader}


async def ingest_pdf(pdf_path: Path, force: bool = False) -> bool:
    """Ingest one PDF.  Returns True if a new record was created."""
    h = _sha256(pdf_path)
    existing = db.fetchone("SELECT id, status FROM documents WHERE sha256 = ?", (h,))

    if existing and not force:
        print(f"  [skip] {pdf_path.name} — already in DB (id={existing['id']})")
        return False

    if existing and force:
        # Clean up previous records
        doc_id = existing["id"]
        for tbl in ("pages", "chunks", "rules", "refs", "review_queue"):
            db.execute(f"DELETE FROM {tbl} WHERE document_id = ?", (doc_id,))
        db.execute("DELETE FROM documents WHERE id = ?", (doc_id,))
        print(f"  [force] removed previous records for {pdf_path.name}")

    print(f"  [read]    {pdf_path.name}")
    pages, ocr = read_pdf(str(pdf_path))

    print(f"  [chunk]   {len(pages)} pages, OCR={'yes' if ocr else 'no'}")
    chunks = chunk_pages(pages)

    print(f"  [extract] calling LLM …")
    try:
        ext = await extract(pages)
    except Exception as exc:
        print(f"  [ERROR]   extraction failed: {exc}")
        return False

    print(f"  [verify]  {len(ext.rules)} rules extracted")
    confidence, reasons = verify(ext, pages)
    print(f"  [verify]  confidence={confidence:.0%}, reasons={reasons}")

    # ── Persist document ──
    doc_id = db.execute(
        """INSERT INTO documents(source_id, url, title, gr_number, gr_date, doc_type,
               scheme, department, file_path, sha256, detected_at, live_at,
               status, ocr_used, confidence, summary_mr, summary_en)
           VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'live', ?, ?, ?, ?)""",
        (
            f"seed://{pdf_path.name}",
            ext.title,
            ext.gr_number,
            ext.gr_date,
            ext.doc_type,
            ext.scheme or SCHEME,
            ext.department,
            str(pdf_path),
            h,
            db.now(),
            db.now(),
            int(ocr),
            confidence,
            ext.summary_mr,
            ext.summary_en,
        ),
    )

    # ── Pages ──
    db.executemany(
        "INSERT INTO pages(document_id, page_no, text) VALUES (?, ?, ?)",
        [(doc_id, n, t) for n, t in pages],
    )

    # ── Chunks ──
    db.executemany(
        "INSERT INTO chunks(document_id, page_no, text) VALUES (?, ?, ?)",
        [(doc_id, pno, text) for pno, text in chunks],
    )

    # ── Rules (all pre-approved for seed) ──
    for rule in ext.rules:
        db.execute(
            """INSERT INTO rules(document_id, scheme, field, value, unit,
                   condition_text, source_quote, page_no, effective_from,
                   grounded, status)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'approved')""",
            (
                doc_id,
                ext.scheme or SCHEME,
                rule.field,
                rule.value,
                rule.unit,
                rule.condition_text,
                rule.source_quote,
                rule.page_no,
                rule.effective_from,
                int(bool(rule.grounded)),
            ),
        )

    # ── Refs ──
    for ref in ext.refers_to:
        db.execute(
            "INSERT INTO refs(document_id, ref_gr_number, ref_gr_date, relation) VALUES (?,?,?,?)",
            (doc_id, ref.gr_number, ref.gr_date, ref.relation),
        )

    # ── Copy to portal_published so the sample portal lists it ──
    dest = PORTAL_PUB / pdf_path.name
    if not dest.exists():
        shutil.copy2(pdf_path, dest)

    print(f"  [done]    doc_id={doc_id}, gr={ext.gr_number}, date={ext.gr_date}")
    return True


async def main(force: bool = False) -> None:
    pdfs = sorted(PDFS_SEED.glob("*.pdf"))
    if not pdfs:
        print(
            f"No PDFs found in {PDFS_SEED}.\n"
            "Place your downloaded GR files there and re-run this script."
        )
        return

    manifest = _load_manifest()
    print(f"Found {len(pdfs)} PDFs in pdfs_seed/. Manifest has {len(manifest)} entries.\n")

    ingested = 0
    for i, pdf in enumerate(pdfs):
        print(f"── {pdf.name}")
        ok = await ingest_pdf(pdf, force=force)
        if ok:
            ingested += 1

    if ingested:
        print(f"\nBuilding search index for {ingested} new document(s) …")
        await INDEX.build_async()
        print("Index ready.")
    else:
        print("\nNothing new to ingest.")

    print("\nSeed complete.")


if __name__ == "__main__":
    force = "--force" in sys.argv
    asyncio.run(main(force=force))
