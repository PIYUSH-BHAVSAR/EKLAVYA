"""Evaluation runner: runs the 20-question set and records scores."""
from __future__ import annotations

import json
from pathlib import Path

from . import db
from .answer import ask
from .config import EVAL_DIR
from .textutil import norm


async def run_eval() -> int:
    """Run the evaluation question set and return the eval run id."""
    questions_path = EVAL_DIR / "questions.json"
    if not questions_path.exists():
        raise FileNotFoundError(f"Eval questions not found at {questions_path}")

    items: list[dict] = json.loads(questions_path.read_text(encoding="utf-8"))
    run_id = db.execute("INSERT INTO eval_runs(ts, total, passed, citation_ok) VALUES (?,0,0,0)",
                        (db.now(),))

    passed = 0
    cite_ok_total = 0

    for item in items:
        res = await ask(item["question"], username="eval")

        if item.get("expected_refusal"):
            ok = bool(res["refused"])
            c_ok = ok
        else:
            expected_gr = norm(item.get("expected_gr", ""))
            c_ok = any(
                expected_gr and expected_gr in norm(c.get("gr_number") or "")
                for c in res["citations"]
            )
            ans = norm(res["answer"])
            expected_vals = item.get("expected_values", [])
            values_found = all(norm(v) in ans for v in expected_vals)
            ok = (not res["refused"]) and c_ok and values_found

        passed += int(ok)
        cite_ok_total += int(c_ok)

        db.execute(
            """INSERT INTO eval_results(run_id, qid, question, answer, refused,
                   citation_ok, answer_ok, note)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (run_id, item.get("id", ""), item["question"], res["answer"],
             int(res["refused"]), int(c_ok), int(ok), item.get("note", "")),
        )

    db.execute(
        "UPDATE eval_runs SET total=?, passed=?, citation_ok=? WHERE id=?",
        (len(items), passed, cite_ok_total, run_id),
    )
    return run_id
