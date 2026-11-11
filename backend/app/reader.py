"""PDF reader: extracts text per page, falls back to Tesseract OCR when needed.

Heuristic for "garbled text":
- If the page yields < 80 characters after stripping, assume it's an image page.
- If the character distribution looks like a legacy Latin-encoded Devanagari font
  (lots of Latin chars, almost no Unicode Devanagari codepoints, and the text is
  not recognisable English), force OCR.
"""
import io
import fitz          # PyMuPDF
import pytesseract
from PIL import Image

# Common English words that would indicate the page really is English, not garbled Devanagari
_COMMON_EN = {
    "the", "and", "of", "to", "government", "for", "is", "in", "a", "an",
    "that", "this", "with", "be", "as", "at", "by", "from", "are", "or",
    "resolution", "maharashtra", "department", "scheme", "subject",
}


def _garbled(text: str) -> bool:
    """Return True if `text` looks like a legacy-font encoding of Devanagari.

    We check:
    1. Too few characters overall (image or blank page).
    2. Very high Latin fraction but very low Devanagari fraction AND the text
       cannot be explained as legitimate English content.
    """
    letters = [c for c in text if c.isalpha() or "\u0900" <= c <= "\u097F"]
    if len(letters) < 20:
        return True  # near-blank page

    dev_count = sum(1 for c in letters if "\u0900" <= c <= "\u097F")
    latin_count = sum(1 for c in letters if c.isascii() and c.isalpha())

    dev_ratio = dev_count / len(letters)
    latin_ratio = latin_count / len(letters)

    words = text.lower().split()
    english_hits = sum(1 for w in words if w in _COMMON_EN)

    # If it has real Devanagari → it's fine
    if dev_ratio >= 0.05:
        return False
    # If it looks heavily Latin but has recognisable English → it really is English
    if latin_ratio > 0.6 and english_hits >= 3:
        return False
    # High Latin, no Devanagari, not recognisable English → legacy font
    if latin_ratio > 0.6:
        return True
    return False


def read_pdf(path: str) -> tuple[list[tuple[int, str]], bool]:
    """Read a PDF and return ([(page_no, text), ...], ocr_used).

    page_no is 1-indexed.  If any page needed OCR, ocr_used is True.
    """
    doc = fitz.open(path)
    out: list[tuple[int, str]] = []
    ocr_used = False

    for i, page in enumerate(doc, start=1):
        text = page.get_text().strip()

        if len(text) < 80 or _garbled(text):
            # Render at 200 DPI and OCR with Marathi + English
            pix = page.get_pixmap(dpi=200)
            img = Image.open(io.BytesIO(pix.tobytes("png")))
            try:
                text = pytesseract.image_to_string(img, lang="mar+eng").strip()
            except pytesseract.TesseractNotFoundError:
                # Tesseract not installed — warn and keep whatever native text we have
                text = text or f"[OCR unavailable for page {i}]"
            except Exception as exc:  # noqa: BLE001
                text = text or f"[OCR error on page {i}: {exc}]"
            ocr_used = True

        out.append((i, text))

    return out, ocr_used
