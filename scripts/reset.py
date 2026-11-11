#!/usr/bin/env python3
"""Demo reset script — restores the app to its seed state.

Steps:
1. Delete eklavya.db and recreate schema.
2. Clear data/archive/ and data/portal_published/.
3. Copy all data/pdfs_seed/* into data/portal_published/.
4. Re-run the seed ingestion pipeline.
5. (Kept) pdfs_held/ is untouched — the held PDF stays held.

Usage:
    cd eklavya
    python -m scripts.reset
"""
from __future__ import annotations

import asyncio
import shutil
import sys
from pathlib import Path

_BACKEND = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(_BACKEND))

from app.config import ARCHIVE_DIR, DB_PATH, PDFS_SEED, PORTAL_PUB  # noqa: E402


async def reset() -> None:
    import time
    t0 = time.time()

    # ── 1. Wipe and recreate the database ──
    if DB_PATH.exists():
        DB_PATH.unlink()
        print("Deleted old database.")

    # Import db AFTER deleting so init() runs on the fresh file
    from app import db  # noqa: PLC0415
    db.init()
    print("Database recreated.")

    # ── 2. Clear archive and portal_published ──
    for directory in [ARCHIVE_DIR, PORTAL_PUB]:
        for f in directory.glob("*"):
            if f.is_file():
                f.unlink()
    print("Cleared archive/ and portal_published/.")

    # ── 3. Copy seed PDFs to portal_published ──
    pdfs = list(PDFS_SEED.glob("*.pdf"))
    for pdf in pdfs:
        shutil.copy2(pdf, PORTAL_PUB / pdf.name)
    print(f"Copied {len(pdfs)} seed PDF(s) to portal_published/.")

    # ── 4. Re-seed ──
    # Import seed after db reset so it sees the fresh DB
    # sys.path already has backend/ prepended; add project root for scripts.*
    _ROOT = Path(__file__).resolve().parents[1]
    if str(_ROOT) not in sys.path:
        sys.path.insert(0, str(_ROOT))

    from scripts.seed import ingest_pdf  # noqa: PLC0415
    from app.index import INDEX  # noqa: PLC0415

    ingested = 0
    for pdf in sorted(pdfs):
        print(f"  Ingesting {pdf.name} …")
        ok = await ingest_pdf(pdf, force=False)
        if ok:
            ingested += 1

    if ingested:
        await INDEX.build_async()
        print(f"Search index built ({ingested} document(s)).")

    elapsed = time.time() - t0
    print(f"\nReset complete in {elapsed:.1f} s.")


if __name__ == "__main__":
    asyncio.run(reset())
