#!/usr/bin/env python3
"""Quick smoke test for a PDF: prints page number, character count, and the
first 120 characters of each page.

Usage:
    cd eklavya
    python -m scripts.smoke_pdf data/pdfs_seed/gr_001.pdf
"""
import sys
from pathlib import Path

_BACKEND = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(_BACKEND))

import fitz  # noqa: E402


def main(pdf_path: str) -> None:
    doc = fitz.open(pdf_path)
    for i, page in enumerate(doc, start=1):
        text = page.get_text()
        print(f"Page {i:>3}  chars={len(text):>6}  {repr(text[:120])}")
    print(f"\nTotal pages: {len(doc)}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python -m scripts.smoke_pdf <path/to/file.pdf>")
        sys.exit(1)
    main(sys.argv[1])
