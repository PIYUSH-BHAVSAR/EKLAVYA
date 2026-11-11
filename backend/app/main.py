"""FastAPI application entry point — fully offline mode.

Start with:
    cd eklavya/backend
    uvicorn app.main:app --reload --port 8000

Startup sequence:
  1. DB schema init.
  2. Verify Ollama is reachable and model exists.
  3. Load model into VRAM (keep_alive: -1).
  4. Run one warm-up generation to confirm the pipeline works.
  5. Build the retrieval index (embedding model loaded here too).
  6. Start background keepalive task (polls /api/ps every 3 min).
"""
from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from . import db
from .config import ARCHIVE_DIR, OFFLINE_MODE
from .index import INDEX
from .llm import check_ollama_reachable, close_client, ps_status, warm_up
from .portal import router as portal_router
from .routes_admin import router as admin_router
from .routes_public import router as public_router

log = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(name)s  %(message)s")


# ---------------------------------------------------------------------------
# Background keepalive task
# ---------------------------------------------------------------------------

_keepalive_task: asyncio.Task | None = None


async def _keepalive_loop() -> None:
    """Every 3 minutes: check if model is still in VRAM; reload if evicted."""
    interval = 180
    while True:
        try:
            await asyncio.sleep(interval)
            ps = await ps_status()
            if not ps:
                log.warning("[keepalive] model not in /api/ps — reloading …")
                await warm_up()
                log.info("[keepalive] model reloaded")
            else:
                log.debug("[keepalive] model OK, size_vram=%s", ps.get("size_vram"))
        except asyncio.CancelledError:
            break
        except Exception as exc:
            log.warning("[keepalive] error: %s", exc)


# ---------------------------------------------------------------------------
# Startup / shutdown
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    global _keepalive_task

    # 1. DB
    db.init()
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)

    # 2. Verify Ollama is reachable
    if OFFLINE_MODE:
        log.info("[startup] OFFLINE_MODE=1 — only localhost LLM calls permitted")
    try:
        await check_ollama_reachable()
    except RuntimeError as exc:
        log.error("[startup] %s", exc)
        log.error("[startup] Continuing without LLM — chat and pipeline will fail until Ollama is running")
    else:
        # 3+4. Load model + warm-up generation
        try:
            elapsed = await warm_up()
            log.info("[startup] Model loaded in memory (%.1f s)", elapsed)
        except Exception as exc:
            log.error("[startup] warm-up failed: %s", exc)

    # 5. Build retrieval index (loads sentence-transformers encoder)
    try:
        await INDEX.build_async()
        log.info("[startup] Retrieval index built (%d chunks)", len(INDEX.rows))
    except Exception as exc:
        log.error("[startup] index build failed: %s", exc)

    # 6. Start keepalive background task
    _keepalive_task = asyncio.create_task(_keepalive_loop())
    log.info("[startup] Keepalive task started (interval: 3 min)")

    yield

    # Shutdown
    if _keepalive_task:
        _keepalive_task.cancel()
        try:
            await _keepalive_task
        except asyncio.CancelledError:
            pass
    await close_client()
    log.info("[shutdown] httpx client closed")


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(
    title="EKLAVYA",
    description="Government Resolution assistant — offline prototype",
    version="0.2.0",
    lifespan=lifespan,
)

# ---------------------------------------------------------------------------
# CORS
# ---------------------------------------------------------------------------

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:4173",
        "http://localhost:3000",
        "http://localhost:8000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------

app.include_router(public_router,  prefix="/api")
app.include_router(admin_router,   prefix="/api")
app.include_router(portal_router)   # /mock-portal/... (no prefix)

# ---------------------------------------------------------------------------
# Static: archived PDFs  →  /files/<name>.pdf
# ---------------------------------------------------------------------------

ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/files", StaticFiles(directory=str(ARCHIVE_DIR)), name="files")

# ---------------------------------------------------------------------------
# Serve React SPA (production build)
# ---------------------------------------------------------------------------

_WEB_DIST = Path(__file__).resolve().parents[3] / "web" / "dist"

if _WEB_DIST.exists():
    from fastapi.responses import FileResponse

    app.mount("/assets", StaticFiles(directory=str(_WEB_DIST / "assets")), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    def spa_fallback(full_path: str):
        return FileResponse(str(_WEB_DIST / "index.html"))
