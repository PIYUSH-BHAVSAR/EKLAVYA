"""
LLM client — Ollama only, fully offline.

Key design decisions:
- ONE shared httpx.AsyncClient for the whole process lifetime.
- ONE asyncio.Lock so Ollama (single-GPU) handles one request at a time.
- IDENTICAL options dict on every call: num_ctx + temperature + thinking=false.
  Changing num_ctx forces a full model reload; we never vary it.
- keep_alive: -1 on every request keeps the model resident forever.
- thinking=false: gemma4 defaults thinking to true which injects <think>…</think>
  tokens that break JSON parsing; we always disable it.
- Disk cache in data/llm_cache for extraction calls so re-seeding costs 0 LLM calls.
- Timeouts: 300 s for the first/cold load, 120 s for normal requests.
  We detect "cold" by checking _stats.load_duration_ms after each call.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import pathlib
import re
import time
from typing import Any

import httpx

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration (all from environment; set in .env or at process startup)
# ---------------------------------------------------------------------------

OLLAMA_HOST: str   = os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434")
OLLAMA_MODEL: str  = os.getenv("OLLAMA_MODEL", "gemma4:e2b-it-qat")
OLLAMA_NUM_CTX: int = int(os.getenv("OLLAMA_NUM_CTX", "8192"))

# These options are sent on EVERY request, unchanged.
# Changing num_ctx mid-session causes a full model reload.
OLLAMA_OPTIONS: dict[str, Any] = {
    "num_ctx":     OLLAMA_NUM_CTX,
    "temperature": 0,
    # Note: gemma4:e2b-it-qat routes its reasoning to message.thinking regardless
    # of this flag.  We leave thinking enabled and read whichever field has content.
}

# ---------------------------------------------------------------------------
# Shared state
# ---------------------------------------------------------------------------

CACHE_DIR = pathlib.Path(__file__).resolve().parents[2] / "data" / "llm_cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

_lock  = asyncio.Lock()          # serialise all Ollama calls (one at a time)
_queue_len: int = 0              # approximate waiters (informational)

# Singleton httpx client — created once, reused across all calls
_client: httpx.AsyncClient | None = None


def _get_client() -> httpx.AsyncClient:
    global _client
    if _client is None:
        _client = httpx.AsyncClient(
            base_url=OLLAMA_HOST,
            timeout=httpx.Timeout(300.0, connect=10.0),
        )
    return _client


async def close_client() -> None:
    """Call this on application shutdown."""
    global _client
    if _client is not None:
        await _client.aclose()
        _client = None


# ---------------------------------------------------------------------------
# Per-request stats (updated after each call, readable via /api/system/llm)
# ---------------------------------------------------------------------------

class _Stats:
    def __init__(self) -> None:
        self.last_latency_ms: int        = 0
        self.last_tokens_per_sec: float  = 0.0
        self.last_load_duration_ms: int  = 0
        self.last_total_duration_ms: int = 0
        self.loaded: bool                = False
        self.load_time_s: float          = 0.0   # wall time for cold load

    def update(self, resp: dict, wall_ms: int) -> None:
        self.last_latency_ms        = wall_ms
        self.last_total_duration_ms = int(resp.get("total_duration", 0) / 1_000_000)
        self.last_load_duration_ms  = int(resp.get("load_duration",  0) / 1_000_000)
        ec = resp.get("eval_count",    0) or 0
        ed = resp.get("eval_duration", 0) or 0
        self.last_tokens_per_sec = round(ec / (ed / 1e9), 1) if ed > 0 and ec > 0 else 0.0

    def log_call(self, label: str) -> None:
        ld = self.last_load_duration_ms
        log.info(
            "[ollama] %s  latency=%d ms  load=%d ms  tps=%.1f  ctx=%d",
            label, self.last_latency_ms, ld, self.last_tokens_per_sec, OLLAMA_NUM_CTX,
        )
        if ld > 500:
            log.warning("[ollama] HIGH load_duration=%d ms — model may have reloaded!", ld)


_stats = _Stats()


def get_stats() -> _Stats:
    return _stats


def queue_length() -> int:
    return _queue_len


# ---------------------------------------------------------------------------
# JSON extraction helper
# ---------------------------------------------------------------------------

_JSON_RE = re.compile(r"\{.*\}", re.S)


def _repair_truncated_json(text: str) -> str:
    """
    Attempt to repair a JSON object that was cut off by a token limit.
    Strategy: find the last complete key-value pair, close all open
    brackets/braces, and return a valid (possibly incomplete) object.
    """
    # Strip any trailing partial string: find last complete "..." value
    # by walking back from the end to the last comma or opening brace
    # at the top level, then close open structures.

    # Count unclosed braces and brackets
    depth_brace   = 0
    depth_bracket = 0
    in_string     = False
    escape_next   = False
    last_safe_pos = 0   # position after the last complete top-level value

    for i, ch in enumerate(text):
        if escape_next:
            escape_next = False
            continue
        if ch == "\\" and in_string:
            escape_next = True
            continue
        if ch == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch == '{':
            depth_brace += 1
        elif ch == '}':
            depth_brace -= 1
            if depth_brace == 0:
                last_safe_pos = i + 1
        elif ch == '[':
            depth_bracket += 1
        elif ch == ']':
            depth_bracket -= 1

    if depth_brace == 0 and depth_bracket == 0 and not in_string:
        return text   # already valid

    # Truncate to last complete top-level object if we found one
    if last_safe_pos > 0:
        return text[:last_safe_pos]

    # Otherwise: find last complete comma-separated entry and close structures
    # Trim back to the last ',' or '{' not inside a string
    trimmed = text.rstrip()
    # Remove trailing partial token (unfinished string or key)
    if in_string or trimmed.endswith('"') or ':' in trimmed[-20:]:
        # cut back to last comma outside strings
        for i in range(len(trimmed) - 1, -1, -1):
            if trimmed[i] == ',' :
                trimmed = trimmed[:i]
                break

    # Close open arrays then objects
    trimmed += "]" * depth_bracket + "}" * depth_brace
    return trimmed


def _parse_json(text: str) -> dict:
    # Strip any stray <think>…</think> block that slipped through
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.S).strip()

    # First try: valid JSON as-is
    m = _JSON_RE.search(text)
    if m:
        try:
            return json.loads(m.group(0))
        except json.JSONDecodeError:
            pass

    # Second try: repair truncated output
    try:
        repaired = _repair_truncated_json(text)
        m2 = _JSON_RE.search(repaired)
        if m2:
            return json.loads(m2.group(0))
    except (json.JSONDecodeError, Exception):
        pass

    raise ValueError("no valid JSON object in reply: " + text[:300])


# ---------------------------------------------------------------------------
# Core complete() — all callers go through here
# ---------------------------------------------------------------------------

async def complete(
    system: str,
    user: str,
    json_mode: bool = False,
    max_tokens: int = 3000,
    use_cache: bool = False,
    schema: dict | None = None,
) -> dict | str:
    """
    Send a chat completion to Ollama.

    - system prompt goes first (helps prefix-caching in llama.cpp).
    - user prompt last.
    - keep_alive: -1 always — model stays resident.
    - OLLAMA_OPTIONS sent unchanged every call.
    - schema: pass a JSON Schema dict for Ollama structured outputs;
              if None and json_mode=True, pass format="json".
    """
    global _queue_len

    # Cache lookup (extraction calls with use_cache=True)
    key = hashlib.sha256(
        json.dumps([system, user, json_mode, schema], ensure_ascii=False).encode()
    ).hexdigest()
    cache_file = CACHE_DIR / f"{key}.json"
    if use_cache and cache_file.exists():
        cached = json.loads(cache_file.read_text(encoding="utf-8"))["text"]
        return _parse_json(cached) if (json_mode or schema) else cached

    # Build request body
    body: dict[str, Any] = {
        "model":      OLLAMA_MODEL,
        "messages":   [
            {"role": "system", "content": system},
            {"role": "user",   "content": user},
        ],
        "stream":     False,
        "keep_alive": -1,               # keep model in VRAM forever
        "options":    {                 # IDENTICAL on every call — never vary num_ctx
            **OLLAMA_OPTIONS,
            "num_predict": max_tokens,  # only this varies per call
        },
    }

    if schema is not None:
        body["format"] = schema          # Ollama structured output (JSON Schema)
    elif json_mode:
        body["format"] = "json"

    # Serialise access to the model
    _queue_len += 1
    t0 = time.monotonic()
    try:
        async with _lock:
            _queue_len = max(0, _queue_len - 1)
            # Use a longer timeout if the model might not be loaded yet
            timeout = 300.0 if not _stats.loaded else 120.0
            client = _get_client()
            r = await client.post(
                "/api/chat",
                json=body,
                timeout=timeout,
            )
    except httpx.TimeoutException as exc:
        raise RuntimeError(f"Ollama request timed out ({timeout:.0f} s)") from exc
    except httpx.ConnectError as exc:
        raise RuntimeError(
            "Cannot reach Ollama at " + OLLAMA_HOST +
            " — is `ollama serve` running?"
        ) from exc
    finally:
        _queue_len = max(0, _queue_len - 1)  # guard against double-decrement

    wall_ms = int((time.monotonic() - t0) * 1000)

    if r.status_code != 200:
        raise RuntimeError(f"Ollama HTTP {r.status_code}: {r.text[:400]}")

    resp_data = r.json()
    _stats.update(resp_data, wall_ms)
    _stats.loaded = True
    _stats.log_call(f"json_mode={json_mode or schema is not None}")

    msg: dict = resp_data.get("message", {})
    text: str = msg.get("content", "")

    # gemma4:e2b-it-qat routes ALL output through message.thinking when it
    # decides to think.  If content is empty, fall back to the thinking field.
    if not text.strip():
        text = msg.get("thinking", "")

    if json_mode or schema is not None:
        try:
            out = _parse_json(text)
        except (ValueError, json.JSONDecodeError) as first_err:
            # One retry: ask explicitly to output only JSON
            log.warning("[ollama] JSON parse failed (%s); retrying with explicit JSON reminder", first_err)
            retry_body = dict(body)
            retry_body["messages"] = [
                {"role": "system",    "content": system},
                {"role": "user",      "content": user},
                {"role": "assistant", "content": text},
                {"role": "user",      "content":
                    "Your previous reply was not valid JSON. "
                    "Output ONLY the JSON object, nothing else."},
            ]
            async with _lock:
                r2 = await client.post("/api/chat", json=retry_body, timeout=120.0)
            if r2.status_code == 200:
                text = r2.json()["message"]["content"]
                out = _parse_json(text)
            else:
                raise RuntimeError(f"Ollama retry HTTP {r2.status_code}") from first_err
        if use_cache:
            cache_file.write_text(
                json.dumps({"text": text}, ensure_ascii=False), encoding="utf-8"
            )
        return out

    if use_cache:
        cache_file.write_text(
            json.dumps({"text": text}, ensure_ascii=False), encoding="utf-8"
        )
    return text


# ---------------------------------------------------------------------------
# Backwards-compatible wrapper (kept so existing call sites don't need changes)
# ---------------------------------------------------------------------------

async def complete_with_retry(
    system: str,
    user: str,
    json_mode: bool = False,
    retries: int | None = None,   # ignored — Ollama is local, retries handled inside
    **kw,
) -> dict | str:
    return await complete(system, user, json_mode, **kw)


# ---------------------------------------------------------------------------
# Warm-up helpers (called from main.py lifespan)
# ---------------------------------------------------------------------------

async def check_ollama_reachable() -> None:
    """Verify Ollama is up and the model is available. Raises on failure."""
    try:
        r = await _get_client().get("/api/tags", timeout=10.0)
    except Exception as exc:
        raise RuntimeError(
            f"Ollama not reachable at {OLLAMA_HOST}: {exc}"
        ) from exc
    if r.status_code != 200:
        raise RuntimeError(f"Ollama /api/tags returned HTTP {r.status_code}")
    tags = r.json()
    names = [m["name"] for m in tags.get("models", [])]
    # Accept both "gemma4:e2b-it-qat" and bare "gemma4"
    if not any(OLLAMA_MODEL in n or n in OLLAMA_MODEL for n in names):
        raise RuntimeError(
            f"Model '{OLLAMA_MODEL}' not found in Ollama. "
            f"Available: {names}. Run: ollama pull {OLLAMA_MODEL}"
        )
    log.info("[ollama] reachable; model '%s' found in tags", OLLAMA_MODEL)


async def warm_up() -> float:
    """
    Load model into VRAM and run a 1-token generation to confirm it works.
    Returns wall-clock seconds for the full load.
    """
    log.info("[ollama] Loading model '%s' into memory …", OLLAMA_MODEL)
    t0 = time.monotonic()

    # Step 1: pre-load via /api/generate keep_alive trick
    try:
        r = await _get_client().post(
            "/api/generate",
            json={
                "model":      OLLAMA_MODEL,
                "prompt":     "",
                "keep_alive": -1,
                "options":    OLLAMA_OPTIONS,
            },
            timeout=300.0,
        )
        if r.status_code != 200:
            log.warning("[ollama] warm-up /api/generate returned %d", r.status_code)
    except Exception as exc:
        log.warning("[ollama] warm-up pre-load failed: %s", exc)

    # Step 2: 1-token real generation to confirm the pipeline works
    try:
        await complete(
            system="You are a helpful assistant.",
            user="Reply with the single word: ready",
            max_tokens=4,
        )
    except Exception as exc:
        log.warning("[ollama] warm-up generation failed: %s", exc)

    elapsed = time.monotonic() - t0
    _stats.load_time_s = elapsed
    _stats.loaded = True
    log.info("[ollama] Model loaded in memory (%.1f s)", elapsed)
    return elapsed


async def ps_status() -> dict:
    """Return the current /api/ps entry for our model (or {} if not loaded)."""
    try:
        r = await _get_client().get("/api/ps", timeout=10.0)
        if r.status_code != 200:
            return {}
        for m in r.json().get("models", []):
            if OLLAMA_MODEL in m.get("name", ""):
                return m
    except Exception:
        pass
    return {}
