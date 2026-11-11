"""Seed script: directly ingest all PDFs from data/pdfs_seed/ into the database.

Bypasses the portal fetch stage and processes each PDF through:
  archive -> read -> extract -> verify -> insert -> index

Run from eklavya/backend/:
    python scripts/seed.py
    python scripts/seed.py --force   # wipe DB first and re-ingest
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import shutil
import sys
import time
from pathlib import Path

# Ensure app package is importable when running as a script from backend/
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import db
from app.chunker import chunk_pages
from app.config import ARCHIVE_DIR, PDFS_SEED, SCHEME, DB_PATH
from app.extractor import extract
from app.index import INDEX
from app.reader import read_pdf
from app.verifier import verify


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


async def ingest_pdf(pdf_path: Path, source_id: int) -> bool:
    """Ingest one PDF. Returns True if newly added, False if skipped."""
    sha = _sha256(pdf_path)

    # Skip if already ingested (idempotent on re-run without --force)
    existing = db.fetchone("SELECT id, status FROM documents WHERE sha256 = ?", (sha,))
    if existing:
        print(f"  [skip] already in DB  status={existing['status']}")
        return False

    t0 = time.time()

    # --- archive ---
    archive_path = ARCHIVE_DIR / pdf_path.name
    if not archive_path.exists():
        shutil.copy2(pdf_path, archive_path)

    # --- read ---
    print("  [read]    reading pages ...")
    pages, ocr_used = await asyncio.to_thread(read_pdf, str(pdf_path))
    print(f"  [read]    {len(pages)} pages extracted  ocr={ocr_used}")

    # --- extract (LLM with disk cache) ---
    print("  [extract] calling LLM ...")
    try:
        extraction = await extract(pages)
    except Exception as e:
        print(f"  [ERROR]   extraction failed: {e}")
        return False

    print(f"  [extract] gr={extraction.gr_number}  type={extraction.doc_type}  rules={len(extraction.rules)}")

    # --- verify (grounding check) ---
    confidence, reasons = verify(extraction, pages)
    grounded_pct = f"{confidence:.0%}"
    if reasons:
        print(f"  [verify]  confidence={grounded_pct}  flags={reasons}")
    else:
        print(f"  [verify]  confidence={grounded_pct}  OK")

    # --- insert document ---
    doc_id = db.execute(
        """INSERT INTO documents
           (source_id, url, title, gr_number, gr_date, doc_type, scheme, department,
            file_path, sha256, detected_at, live_at, status, ocr_used,
            confidence, summary_mr, summary_en)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            source_id,
            pdf_path.as_uri(),
            extraction.title,
            extraction.gr_number,
            extraction.gr_date,
            extraction.doc_type,
            extraction.scheme,
            extraction.department,
            str(archive_path),
            sha,
            db.now(),
            db.now(),
            "live",
            1 if ocr_used else 0,
            confidence,
            extraction.summary_mr,
            extraction.summary_en,
        ),
    )

    # --- insert rules ---
    for rule in extraction.rules:
        db.execute(
            """INSERT INTO rules
               (document_id, scheme, field, value, unit, condition_text,
                source_quote, page_no, effective_from, grounded, status)
               VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (
                doc_id,
                SCHEME,
                rule.field,
                rule.value,
                rule.unit,
                rule.condition_text,
                rule.source_quote,
                rule.page_no,
                rule.effective_from,
                1 if rule.grounded else 0,
                "approved",
            ),
        )

    # --- insert cross-references ---
    for ref in extraction.refers_to:
        db.execute(
            "INSERT INTO refs (document_id, ref_gr_number, ref_gr_date, relation) VALUES (?,?,?,?)",
            (doc_id, ref.gr_number, ref.gr_date, ref.relation),
        )

    # --- store page text (for source viewer / citations) ---
    for page_no, text in pages:
        db.execute(
            "INSERT INTO pages (document_id, page_no, text) VALUES (?,?,?)",
            (doc_id, page_no, text),
        )

    # --- chunk and insert (INDEX.build() reads chunks from DB) ---
    print("  [index]   chunking ...")
    chunk_list = chunk_pages(pages)
    for page_no, chunk_text in chunk_list:
        db.execute(
            "INSERT INTO chunks (document_id, page_no, text, embedding) VALUES (?,?,?,NULL)",
            (doc_id, page_no, chunk_text),
        )

    elapsed = time.time() - t0
    print(f"  [done]    doc_id={doc_id}  chunks={len(chunk_list)}  elapsed={elapsed:.1f}s")
    return True


async def main(force: bool) -> None:
    if force:
        print("[seed] --force: deleting database and LLM cache")
        if DB_PATH.exists():
            DB_PATH.unlink()
        from app.llm import CACHE_DIR
        if CACHE_DIR.exists():
            shutil.rmtree(CACHE_DIR)
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
        db.init()

    db.init()  # ensure schema exists

    source = db.fetchone("SELECT id FROM sources WHERE kind='sample'")
    if not source:
        db.init()
        source = db.fetchone("SELECT id FROM sources WHERE kind='sample'")
    source_id = source["id"]

    pdfs = sorted(PDFS_SEED.glob("*.pdf"))
    if not pdfs:
        print(f"[seed] No PDFs found in {PDFS_SEED}")
        print("       Place GR PDFs in eklavya/data/pdfs_seed/")
        sys.exit(1)

    print(f"[seed] {len(pdfs)} PDFs found  source_id={source_id}  db={DB_PATH}")
    print()

    added = 0
    for i, pdf in enumerate(pdfs, 1):
        print(f"[{i}/{len(pdfs)}] {pdf.name}")
        ok = await ingest_pdf(pdf, source_id)
        if ok:
            added += 1
        print()

    print("[seed] Building in-memory index ...")
    await INDEX.build_async()

    total_docs   = db.fetchone("SELECT COUNT(*) AS n FROM documents WHERE status='live'")["n"]
    total_rules  = db.fetchone("SELECT COUNT(*) AS n FROM rules WHERE status='approved'")["n"]
    total_chunks = db.fetchone("SELECT COUNT(*) AS n FROM chunks")["n"]

    print()
    print(f"[seed] Done -- {added} new | {total_docs} live docs | {total_rules} rules | {total_chunks} chunks")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed EKLAVYA database from pdfs_seed/")
    parser.add_argument("--force", action="store_true",
                        help="Wipe DB and LLM cache, then re-ingest everything")
    args = parser.parse_args()
    asyncio.run(main(args.force))
