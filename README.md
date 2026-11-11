# EKLAVYA

**Offline government resolution assistant for Maharashtra tribal welfare schemes.**

EKLAVYA lets citizens ask questions in Marathi or English and get answers grounded in official Government Resolutions (GRs) published by the Maharashtra Tribal Development Department (Shabari Adivasi Finance & Development Corporation). Everything — the LLM, the embedding model, the database — runs on your own machine. No internet connection is required after the one-time setup.

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│  Browser (React + Vite + Tailwind)                      │
│  Citizen chat  ·  Admin pipeline  ·  LLM status chip   │
└──────────────────────┬──────────────────────────────────┘
                       │  HTTP (localhost:8000)
┌──────────────────────▼──────────────────────────────────┐
│  FastAPI backend                                        │
│  answer.py  ·  extractor.py  ·  pipeline.py            │
│  index.py (BM25 + multilingual-e5-small, CPU)          │
│  guardrails.py  ·  auth.py  ·  eval.py                 │
└──────────────────────┬──────────────────────────────────┘
                       │  HTTP (localhost:11434)
┌──────────────────────▼──────────────────────────────────┐
│  Ollama                                                 │
│  gemma4:e2b-it-qat  ·  4.6 B  ·  Q4_0  ·  GPU        │
│  keep_alive: -1  →  stays in VRAM forever              │
└─────────────────────────────────────────────────────────┘
                    SQLite  (data/eklavya.db)
```

**Key design choices:**

- The LLM is loaded once on startup and never reloaded. `keep_alive: -1` and a fixed `num_ctx: 8192` on every request prevent Ollama from evicting the model between calls.
- All LLM calls are serialised through a single `asyncio.Lock` — one request at a time to the GPU.
- Document extraction uses two separate calls per PDF (metadata + rules) with Ollama structured outputs (JSON Schema `format`) for deterministic extraction.
- The answer pipeline uses BM25 + dense retrieval (RRF merge, top 4 chunks), a 120-word answer cap, and a deterministic post-check that rejects answers containing numbers or dates not found verbatim in cited sources.
- `OFFLINE_MODE=1` activates an HTTP guard that raises an error if any code attempts to reach a non-localhost URL.

---

## Requirements

| Component | Version |
|---|---|
| Python | 3.11+ |
| Node.js | 18+ |
| Ollama | 0.3.5+ |
| GPU VRAM | ≥ 4 GB (model is 1.7 GB loaded) |

---

## Setup

### 1. Pull the LLM

```bash
ollama pull gemma4:e2b-it-qat
```

Verify it loads:

```bash
ollama ps
# NAME                 SIZE    PROCESSOR    UNTIL
# gemma4:e2b-it-qat    1.7 GB  100% GPU     ...
```

### 2. Clone and create the Python environment

```bash
git clone <repo-url>
cd eklavya

python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

pip install -r backend/requirements.txt
```

### 3. Configure environment

```bash
cp .env.example .env
# The defaults work out of the box — no keys to fill in.
```

### 4. Download the embedding model (one-time, needs internet)

```bash
python scripts/prefetch_models.py
```

This downloads `intfloat/multilingual-e5-small` (~120 MB) into `./models/`. After this you can go fully offline.

### 5. Seed the database

```bash
# Windows:
$env:HF_HUB_OFFLINE="1"; $env:TRANSFORMERS_OFFLINE="1"
python scripts/seed.py

# macOS/Linux:
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 python scripts/seed.py
```

Processes all PDFs in `data/pdfs_seed/` — runs OCR where needed, extracts structured rules via two LLM calls per document, builds the retrieval index. Cached after the first run.

### 6. Install frontend dependencies

```bash
cd web
npm install
cd ..
```

### 7. Start the backend

```bash
# Windows:
$env:HF_HUB_OFFLINE="1"; $env:TRANSFORMERS_OFFLINE="1"
.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir backend --port 8000 --reload

# macOS/Linux:
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 uvicorn app.main:app --app-dir backend --port 8000 --reload
```

Expected startup log:
```
[startup] OFFLINE_MODE=1 — only localhost LLM calls permitted
[ollama] reachable; model 'gemma4:e2b-it-qat' found in tags
[ollama] Loading model 'gemma4:e2b-it-qat' into memory …
[ollama] Model loaded in memory (8.9 s)
[startup] Retrieval index built (113 chunks)
[startup] Keepalive task started (interval: 3 min)
```

### 8. Start the frontend (dev mode)

```bash
cd web
npm run dev
# → http://localhost:5173
```

---

## Demo credentials

| Role | Username | Password |
|---|---|---|
| Citizen | `citizen` | `citizen123` |
| Admin | `admin` | `admin123` |

---

## Project structure

```
eklavya/
├── backend/
│   ├── app/
│   │   ├── main.py          # FastAPI app, lifespan, startup warm-up
│   │   ├── llm.py           # Ollama client — shared httpx, asyncio lock
│   │   ├── extractor.py     # PDF → structured rules (2-call strategy)
│   │   ├── answer.py        # RAG answer pipeline with post-check
│   │   ├── index.py         # BM25 + dense retrieval (RRF)
│   │   ├── pipeline.py      # Ingestion pipeline (SSE streaming)
│   │   ├── guardrails.py    # PII mask, kill switch, offline HTTP guard
│   │   ├── eval.py          # 20-question evaluation runner
│   │   ├── routes_admin.py  # Admin API + /system/llm status endpoint
│   │   ├── routes_public.py # Public API (login, chat, system/llm)
│   │   ├── config.py        # All env-var config, offline mode
│   │   ├── auth.py          # JWT-free session tokens
│   │   ├── db.py            # SQLite helpers
│   │   ├── reader.py        # PDF text extraction + Tesseract OCR
│   │   ├── chunker.py       # Sliding window chunking
│   │   ├── verifier.py      # Rule grounding verification
│   │   ├── rules.py         # Current rules query
│   │   ├── portal.py        # Mock portal publish
│   │   └── textutil.py      # Marathi text utilities
│   ├── scripts/
│   │   └── probe_llm.py     # Quick Ollama smoke-test
│   └── requirements.txt
├── scripts/
│   ├── seed.py              # Ingest pdfs_seed/ into DB
│   ├── prefetch_models.py   # Download embedding model once
│   ├── reset.py             # Wipe DB and re-seed
│   └── ask.py               # CLI question answering
├── web/                     # React frontend (Vite + Tailwind)
│   ├── src/
│   │   ├── components/
│   │   │   └── LlmStatusChip.tsx   # Polls /api/system/llm every 5s
│   │   └── pages/
│   │       ├── admin/              # Overview, Pipeline, Review, Eval, Guardrails
│   │       └── citizen/            # Chat, Source drawer
│   ├── package.json
│   └── index.html                  # No CDN — fonts bundled via @fontsource
├── data/
│   ├── pdfs_seed/           # Source GR PDFs (tracked in git)
│   └── eval/
│       └── questions.json   # 20-question evaluation set (tracked in git)
├── .env.example             # Template — copy to .env, no secrets needed
└── LICENSE
```

---

## Offline verification

After setup, disconnect Wi-Fi and confirm:

```bash
# Backend starts cleanly
# LLM status chip shows green "Gemma loaded in memory · 1.7 GB · always on"
# Chat answers questions with citations
# Guardrails page shows "Offline mode active · blocked outbound attempts: 0"
```

```bash
# No cloud references in source:
grep -rIn "groq\|googleapis\|generativelanguage\|cdn\." backend/ web/src/
# → zero results
```

---

## Known limits

| Area | Detail |
|---|---|
| **Rules extracted** | Seed GRs are mostly budget/admin orders — few contain structured eligibility rules. The RAG path works correctly from chunk text. |
| **Marathi output** | `gemma4:e2b-it-qat` understands Marathi input but defaults to English output. A language toggle note is appended when this happens. A 27B+ model would produce native Marathi. |
| **Concurrency** | One LLM request at a time (single GPU). Queue length is exposed on `/api/system/llm`. |
| **Answer speed** | ~5–12 seconds per question at 82–93 tokens/sec on GPU. |
| **Context window** | 8192 tokens — covers 4 chunks + rules comfortably. |

---

## License

Apache License 2.0 — see [LICENSE](LICENSE).
