"""
probe_llm.py — quick smoke-test for the local Ollama endpoint.

Usage:
    cd eklavya
    python -m backend.scripts.probe_llm

Prints: model name, response text, load_duration, eval_duration, tokens/sec.
"""
import asyncio
import json
import os
import time

import httpx

HOST  = os.getenv("OLLAMA_HOST",  "http://127.0.0.1:11434")
MODEL = os.getenv("OLLAMA_MODEL", "gemma4:e2b-it-qat")


async def main() -> None:
    body = {
        "model":      MODEL,
        "messages":   [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user",   "content": "In one sentence, what is 2 + 2?"},
        ],
        "stream":     False,
        "keep_alive": -1,
        "options":    {"num_ctx": 512, "temperature": 0, "thinking": False, "num_predict": 32},
    }
    print(f"[probe] POST {HOST}/api/chat  model={MODEL}")
    t0 = time.monotonic()
    async with httpx.AsyncClient(timeout=120.0) as c:
        r = await c.post(f"{HOST}/api/chat", json=body)
    elapsed = time.monotonic() - t0

    if r.status_code != 200:
        print(f"[probe] ERROR HTTP {r.status_code}: {r.text[:400]}")
        return

    d = r.json()
    text = d["message"]["content"]
    load_ms  = int(d.get("load_duration",  0) / 1_000_000)
    total_ms = int(d.get("total_duration", 0) / 1_000_000)
    ec = d.get("eval_count",    0) or 0
    ed = d.get("eval_duration", 0) or 0
    tps = round(ec / (ed / 1e9), 1) if ed > 0 and ec > 0 else 0.0

    print(f"[probe] Response : {text.strip()}")
    print(f"[probe] Wall time: {elapsed*1000:.0f} ms")
    print(f"[probe] Total dur: {total_ms} ms  load_dur: {load_ms} ms")
    print(f"[probe] Tokens/s : {tps}")
    if load_ms > 500:
        print("[probe] WARNING: load_duration > 500 ms — model may not be in memory!")
    else:
        print("[probe] OK: model was already in memory (load_duration ~0)")


if __name__ == "__main__":
    asyncio.run(main())
