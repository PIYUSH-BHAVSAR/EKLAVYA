"""
prefetch_models.py — download sentence-transformers models once into ./models/
before going offline.

Usage (run with Wi-Fi on, before switching to offline):
    cd eklavya
    python scripts/prefetch_models.py

After this script completes:
    - .env has HF_HUB_OFFLINE=1 and HF_HOME=./models
    - The embedding model is cached locally in ./models/
    - The backend can start with no internet connection

The script also verifies that Ollama has the gemma4:e2b-it-qat model loaded.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

# ── Locate project root ────────────────────────────────────────────────────
SCRIPTS_DIR = Path(__file__).resolve().parent
ROOT        = SCRIPTS_DIR.parent          # eklavya/
MODELS_DIR  = ROOT / "models"
MODELS_DIR.mkdir(parents=True, exist_ok=True)

# Point HuggingFace at our local cache (must happen before any imports)
os.environ["HF_HOME"]               = str(MODELS_DIR)
os.environ["HF_HUB_OFFLINE"]        = "0"   # allow download during prefetch
os.environ["TRANSFORMERS_OFFLINE"]  = "0"
os.environ["SENTENCE_TRANSFORMERS_HOME"] = str(MODELS_DIR)

# ── Load .env so EMBED_MODEL is available ─────────────────────────────────
from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

EMBED_MODEL = os.getenv("EMBED_MODEL", "intfloat/multilingual-e5-small")
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "gemma4:e2b-it-qat")


def prefetch_embeddings() -> None:
    print(f"\n[prefetch] Downloading embedding model: {EMBED_MODEL}")
    print(f"[prefetch] Cache directory: {MODELS_DIR}")
    try:
        from sentence_transformers import SentenceTransformer
        model = SentenceTransformer(EMBED_MODEL, cache_folder=str(MODELS_DIR))
        # Quick sanity check
        vec = model.encode(["test sentence"], normalize_embeddings=True)
        print(f"[prefetch] ✓ Embedding model ready — output dim={vec.shape[1]}")
    except ImportError:
        print("[prefetch] ERROR: sentence-transformers not installed.")
        print("           Run: pip install sentence-transformers")
        sys.exit(1)
    except Exception as exc:
        print(f"[prefetch] ERROR downloading embeddings: {exc}")
        sys.exit(1)


def check_ollama() -> None:
    print(f"\n[prefetch] Checking Ollama for model: {OLLAMA_MODEL}")
    import urllib.request, json
    try:
        with urllib.request.urlopen(f"{OLLAMA_HOST}/api/tags", timeout=5) as resp:
            tags = json.loads(resp.read())
        names = [m["name"] for m in tags.get("models", [])]
        found = any(OLLAMA_MODEL in n or n in OLLAMA_MODEL for n in names)
        if found:
            print(f"[prefetch] ✓ Ollama has '{OLLAMA_MODEL}'")
        else:
            print(f"[prefetch] ✗ '{OLLAMA_MODEL}' not found in Ollama.")
            print(f"           Run: ollama pull {OLLAMA_MODEL}")
            print(f"           Available: {names}")
    except Exception as exc:
        print(f"[prefetch] WARNING: Could not reach Ollama at {OLLAMA_HOST}: {exc}")
        print("           Start Ollama before running the backend.")


def main() -> None:
    print("=" * 60)
    print("EKLAVYA — offline model prefetch")
    print("=" * 60)
    prefetch_embeddings()
    check_ollama()
    print("\n[prefetch] All done.")
    print("[prefetch] You can now set HF_HUB_OFFLINE=1 in .env and go offline.")


if __name__ == "__main__":
    main()
