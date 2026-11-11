"""Sample portal: serves a fake department GR listing backed by
data/portal_published/, and a publish-next endpoint that moves one held PDF
into the listing to simulate a new GR appearing.

Routes mounted at /mock-portal by main.py.
"""
from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import httpx
from bs4 import BeautifulSoup
from fastapi import APIRouter
from fastapi.responses import FileResponse, HTMLResponse

from .config import PDFS_HELD, PORTAL_PUB

router = APIRouter()

# In-memory: timestamp when each file was "published" via publish_next
_publish_times: dict[str, datetime] = {}


# ---------------------------------------------------------------------------
# Mock portal listing page
# ---------------------------------------------------------------------------

@router.get("/mock-portal/wcd/", response_class=HTMLResponse)
def listing() -> str:
    """Render an HTML table of PDFs currently in portal_published/."""
    rows = "".join(
        f'<tr>'
        f'<td><a href="/mock-portal/files/{p.name}">{p.stem}</a></td>'
        f'<td>{_fmt_size(p.stat().st_size)}</td>'
        f'</tr>'
        for p in sorted(PORTAL_PUB.glob("*.pdf"))
    )
    return (
        "<html><head><title>WCD GR Listing (Sample)</title></head><body>"
        "<h3>Women and Child Development Department — Government Resolutions (prepared sample)</h3>"
        f"<table border='1' cellpadding='6'>"
        "<tr><th>Document</th><th>Size</th></tr>"
        f"{rows}"
        "</table>"
        "<p><em>This is a prepared sample source, not the official portal.</em></p>"
        "</body></html>"
    )


@router.get("/mock-portal/files/{filename}")
def serve_pdf(filename: str) -> FileResponse:
    path = PORTAL_PUB / filename
    if not path.exists() or not path.suffix.lower() == ".pdf":
        from fastapi import HTTPException
        raise HTTPException(404, "File not found")
    return FileResponse(str(path), media_type="application/pdf")


# ---------------------------------------------------------------------------
# Publish-next helper
# ---------------------------------------------------------------------------

def publish_next() -> Optional[str]:
    """Move the next held PDF into portal_published/.

    Returns the filename that was published, or None if nothing is held.
    """
    held = sorted(PDFS_HELD.glob("*.pdf"))
    if not held:
        return None
    src = held[0]
    dest = PORTAL_PUB / src.name
    dest.write_bytes(src.read_bytes())
    src.unlink()
    _publish_times[src.name] = datetime.now(timezone.utc)
    return src.name


def get_publish_time(filename: str) -> Optional[datetime]:
    return _publish_times.get(filename)


# ---------------------------------------------------------------------------
# Link scraper (used by the pipeline watcher)
# ---------------------------------------------------------------------------

async def list_links(listing_url: str, base_url: str) -> list[str]:
    """Fetch the listing page and return absolute URLs for all PDF hrefs."""
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(listing_url)
        soup = BeautifulSoup(resp.text, "html.parser")
        links = []
        for a in soup.select("a[href$='.pdf']"):
            href = a["href"]
            if href.startswith("http"):
                links.append(href)
            else:
                links.append(base_url.rstrip("/") + "/" + href.lstrip("/"))
        return links
    except Exception as exc:  # noqa: BLE001
        return []


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------

def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _fmt_size(n: int) -> str:
    if n < 1024:
        return f"{n} B"
    if n < 1024 ** 2:
        return f"{n // 1024} KB"
    return f"{n // 1024 ** 2} MB"
