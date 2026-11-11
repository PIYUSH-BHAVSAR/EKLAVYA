"""
Application configuration — fully offline mode.

All external cloud providers (Groq, Gemini, OpenAI) have been removed.
LLM is provided by a local Ollama instance; embeddings by sentence-transformers
from a local ./models cache.
"""
import os
from pathlib import Path

from dotenv import load_dotenv

# config.py lives at eklavya/backend/app/config.py
# parents[0] = app/,  parents[1] = backend/,  parents[2] = eklavya/
ROOT = Path(__file__).resolve().parents[2]   # d:/projects/EKLAVYA/eklavya
load_dotenv(ROOT / ".env")

DATA = ROOT / "data"
DB_PATH = DATA / "eklavya.db"

# ---------------------------------------------------------------------------
# Offline mode
# ---------------------------------------------------------------------------

OFFLINE_MODE: bool = os.getenv("OFFLINE_MODE", "1") not in ("0", "false", "False")

# ---------------------------------------------------------------------------
# Ollama (local LLM)
# ---------------------------------------------------------------------------

OLLAMA_HOST:    str = os.getenv("OLLAMA_HOST",    "http://127.0.0.1:11434")
OLLAMA_MODEL:   str = os.getenv("OLLAMA_MODEL",   "gemma4:e2b-it-qat")
OLLAMA_NUM_CTX: int = int(os.getenv("OLLAMA_NUM_CTX", "8192"))

# ---------------------------------------------------------------------------
# Embeddings — local sentence-transformers, loaded from ./models
# ---------------------------------------------------------------------------

MODELS_DIR = ROOT / "models"
MODELS_DIR.mkdir(parents=True, exist_ok=True)

# Tell HuggingFace to use our local cache and never phone home
os.environ.setdefault("HF_HOME",               str(MODELS_DIR))
os.environ.setdefault("HF_HUB_OFFLINE",        "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE",  "1")
os.environ.setdefault("SENTENCE_TRANSFORMERS_HOME", str(MODELS_DIR))

EMBED_MODEL: str = os.getenv("EMBED_MODEL", "intfloat/multilingual-e5-small")

# ---------------------------------------------------------------------------
# Scheme / department constants
# ---------------------------------------------------------------------------

SCHEME     = "शबरी आदिवासी वित्त व विकास महामंडळ योजना"
DEPARTMENT = "शबरी आदिवासी वित्त व विकास महामंडळ (Shabari Adivasi Finance & Development Corporation)"

# ---------------------------------------------------------------------------
# Demo-only credentials: { username: (password, role) }
# ---------------------------------------------------------------------------

USERS = {
    "citizen": ("citizen123", "citizen"),
    "admin":   ("admin123",   "admin"),
}

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

PDFS_SEED   = DATA / "pdfs_seed"
PDFS_HELD   = DATA / "pdfs_held"
PORTAL_PUB  = DATA / "portal_published"
ARCHIVE_DIR = DATA / "archive"
EVAL_DIR    = DATA / "eval"

# Ensure runtime dirs exist
for _d in [DATA, PDFS_SEED, PDFS_HELD, PORTAL_PUB, ARCHIVE_DIR, EVAL_DIR, MODELS_DIR]:
    _d.mkdir(parents=True, exist_ok=True)
