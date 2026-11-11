#!/usr/bin/env python3
"""CLI smoke-test for the answer engine (Gate A check).

Usage:
    cd eklavya
    python -m scripts.ask "Who is eligible for loans from Shabari Mahamandal?"
    python -m scripts.ask "या महामंडळाच्या कर्जासाठी कोण पात्र आहे?"
    python -m scripts.ask "Has my loan been approved?"   # should refuse
"""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

_BACKEND = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(_BACKEND))

from app import db  # noqa: E402
from app.answer import ask  # noqa: E402
from app.index import INDEX  # noqa: E402


async def main(question: str) -> None:
    # Build the index from whatever is live in the DB
    print("Building index …")
    await INDEX.build_async()
    print(f"Index has {len(INDEX.rows)} chunks.\n")

    result = await ask(question)

    print("=" * 60)
    print(f"QUESTION : {question}")
    print(f"REFUSED  : {result['refused']}")
    print(f"CONFIDENCE: {result['confidence']:.0%}")
    print(f"LATENCY  : {result['latency_ms']} ms")
    print()
    print("ANSWER:")
    print(result["answer"])
    print()
    if result["citations"]:
        print("CITATIONS:")
        for c in result["citations"]:
            print(
                f"  GR {c['gr_number']}  |  {c['gr_date']}  |  page {c['page']}  |  {c['quote'][:80]}…"
            )
    else:
        print("(no citations)")
    print("=" * 60)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python -m scripts.ask \"<question>\"")
        sys.exit(1)
    question = " ".join(sys.argv[1:])
    asyncio.run(main(question))
