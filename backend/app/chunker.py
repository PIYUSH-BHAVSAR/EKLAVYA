"""Chunk page text into overlapping windows for retrieval.

Strategy: slide a character-level window across each page's text.
Chunks stay within a single page so citations always point to a real page number.
"""

DEFAULT_SIZE    = 900   # characters per chunk
DEFAULT_OVERLAP = 150   # overlap between consecutive chunks


def chunk_pages(
    pages: list[tuple[int, str]],
    size: int = DEFAULT_SIZE,
    overlap: int = DEFAULT_OVERLAP,
) -> list[tuple[int, str]]:
    """Return [(page_no, chunk_text), ...].

    Each chunk is at most `size` characters.  Consecutive chunks from the same
    page share `overlap` characters so a sentence split by a window boundary is
    still retrievable.
    """
    out: list[tuple[int, str]] = []
    for page_no, text in pages:
        t = text.strip()
        if not t:
            continue
        i = 0
        while i < len(t):
            chunk = t[i : i + size]
            out.append((page_no, chunk))
            i += size - overlap
    return out
