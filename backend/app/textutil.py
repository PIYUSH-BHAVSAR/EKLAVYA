"""Text normalisation and tokenisation utilities.

Key rules:
- Use the `regex` module (not `re`) so that \\p{L}, \\p{M} etc. work for Devanagari.
- Translate Devanagari digits to ASCII digits so numbers are comparable.
- NFC-normalise so composed and decomposed forms match.
- Do NOT use plain \\w for Marathi: it drops vowel signs (matras) that attach to consonants.
"""
import regex
import unicodedata

# Devanagari digit → ASCII digit translation table
DEV_DIGITS = str.maketrans("०१२३४५६७८९", "0123456789")

# Token pattern: sequences of letters + marks + digits (keeps Devanagari matras)
_TOKEN = regex.compile(r"[\p{L}\p{M}\p{N}]+")


def norm(s: str) -> str:
    """Normalise text: NFC, Devanagari digits → ASCII, collapse whitespace, lowercase."""
    if not s:
        return ""
    s = unicodedata.normalize("NFC", s).translate(DEV_DIGITS)
    return regex.sub(r"\s+", " ", s).strip().lower()


def tokens(s: str) -> list[str]:
    """Return a list of tokens suitable for BM25 indexing."""
    return _TOKEN.findall(norm(s))


def highlight_quote(page_text: str, quote: str, max_context: int = 300) -> str:
    """Return the page_text substring around `quote` with <<<…>>> markers.

    Used to show the grounding context in the review UI.
    """
    if not quote:
        return page_text[:max_context]
    nq = norm(quote)
    np = norm(page_text)
    idx = np.find(nq[:60])  # search by first 60 chars of normalised quote
    if idx == -1:
        return page_text[:max_context]
    start = max(0, idx - 80)
    end = min(len(page_text), idx + len(quote) + 80)
    snippet = page_text[start:end]
    # Insert markers around the quote itself
    qi = snippet.lower().find(quote[:40].lower())
    if qi != -1:
        snippet = snippet[:qi] + "<<<" + snippet[qi:qi + len(quote)] + ">>>" + snippet[qi + len(quote):]
    return snippet
