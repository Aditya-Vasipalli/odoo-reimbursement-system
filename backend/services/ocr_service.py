import io
import re
import shutil
from pathlib import Path
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Iterable

from PIL import Image, ImageEnhance, ImageFilter
import pypdfium2 as pdfium
import pytesseract


def _configure_tesseract_cmd() -> None:
    if shutil.which("tesseract"):
        return

    candidates = [
        Path("C:/Program Files/Tesseract-OCR/tesseract.exe"),
        Path("C:/Program Files (x86)/Tesseract-OCR/tesseract.exe"),
    ]
    for candidate in candidates:
        if candidate.exists():
            pytesseract.pytesseract.tesseract_cmd = str(candidate)
            return


_configure_tesseract_cmd()


AMOUNT_PATTERNS = [
    r"(?:total|amount|amt)\s*[:\-]?\s*([\$\u20b9\u20ac\u00a3]?\s?\d+[\.,]?\d*)",
    r"([\$\u20b9\u20ac\u00a3]\s?\d+[\.,]?\d*)",
]
DATE_PATTERN = r"(\d{2}[/-]\d{2}[/-]\d{4}|\d{4}-\d{2}-\d{2}|[A-Za-z]{3,9}\s+\d{1,2},?\s+\d{4})"
TOTAL_KEYWORDS = ("total", "grand total", "amount", "amount due", "amt")
CURRENCY_HINTS = {
    "$": "USD",
    "\u20b9": "INR",
    "\u20ac": "EUR",
    "\u00a3": "GBP",
}
CURRENCY_CODE_PATTERN = re.compile(r"\b(USD|INR|EUR|GBP)\b", flags=re.IGNORECASE)
NUMBER_PATTERN = re.compile(r"(?<!\d)(\d{1,7}(?:[\.,]\d{1,3})?)(?!\d)")
DECIMAL_OVERLAP_PATTERN = re.compile(r"(?=(\d{2,7}[\.,]\d{1,2}))")


def _infer_expense_type(text: str) -> str | None:
    lower = text.lower()
    if any(word in lower for word in ["restaurant", "cafe", "food", "dine", "meal", "lunch", "dinner"]):
        return "Food"
    if any(word in lower for word in ["taxi", "uber", "ola", "flight", "travel", "bus", "train"]):
        return "Travel"
    if any(word in lower for word in ["office", "stationery", "printer", "supplies"]):
        return "Office"
    return None


def preprocess(image_bytes: bytes) -> Image.Image:
    img = Image.open(io.BytesIO(image_bytes)).convert("L")
    img = img.filter(ImageFilter.SHARPEN)
    enhancer = ImageEnhance.Contrast(img)
    img = enhancer.enhance(2.3)
    width, height = img.size
    if width and height and min(width, height) < 1000:
        scale = max(1000 / float(min(width, height)), 1.0)
        img = img.resize((max(1, int(width * scale)), max(1, int(height * scale))))
    # Binarize to reduce noise and improve OCR consistency on receipts.
    img = img.point(lambda p: 255 if p > 165 else 0)
    return img


def _to_float(raw: str) -> float | None:
    translated = raw.translate(str.maketrans({"O": "0", "o": "0", "I": "1", "l": "1", "S": "5", "s": "5"}))
    cleaned = re.sub(r"[^\d\.,]", "", translated).replace(",", "")
    if not cleaned:
        return None
    try:
        return float(Decimal(cleaned))
    except (InvalidOperation, ValueError):
        return None


def _extract_currency_from_text(text: str) -> str | None:
    for symbol, code in CURRENCY_HINTS.items():
        if symbol in text:
            return code
    if "rs" in text.lower() or "inr" in text.lower():
        return "INR"
    match = CURRENCY_CODE_PATTERN.search(text)
    if match:
        return match.group(1).upper()
    return None


def _candidate_amounts(line: str) -> Iterable[tuple[float, int]]:
    lower = line.lower()
    decimal_candidates = [m.group(1) for m in DECIMAL_OVERLAP_PATTERN.finditer(line)]
    number_candidates = [m.group(1) for m in NUMBER_PATTERN.finditer(line)]

    seen: set[str] = set()
    for raw in decimal_candidates + number_candidates:
        if raw in seen:
            continue
        seen.add(raw)

        amount = _to_float(raw)
        if amount is None:
            continue
        if amount <= 0 or amount > 1_000_000:
            continue

        score = 0
        if any(keyword in lower for keyword in TOTAL_KEYWORDS):
            score += 6
        if any(symbol in line for symbol in CURRENCY_HINTS):
            score += 3
        if CURRENCY_CODE_PATTERN.search(line) or "rs" in lower:
            score += 2
        if re.search(r"\d[\.,]\d{2}(?!\d)", raw):
            score += 2

        has_currency_hint = any(symbol in line for symbol in CURRENCY_HINTS) or bool(CURRENCY_CODE_PATTERN.search(line)) or ("rs" in lower)
        integer_part = raw.split(".")[0].split(",")[0]
        if not has_currency_hint and ("." in raw or "," in raw):
            if len(integer_part) >= 3:
                score -= 2
            if len(integer_part) == 2:
                score += 1

        if amount < 10_000:
            score += 1

        yield amount, score


def _extract_amount_and_currency(lines: list[str], text: str) -> tuple[float | None, str | None]:
    best_amount: float | None = None
    best_score = -1
    best_line = ""

    for line in lines:
        for amount, score in _candidate_amounts(line):
            if score > best_score:
                best_amount = amount
                best_score = score
                best_line = line

    currency = _extract_currency_from_text(best_line) if best_line else None
    if currency is None:
        currency = _extract_currency_from_text(text)

    return best_amount, currency


def _extract_vendor(lines: list[str]) -> str | None:
    for line in lines:
        if any(ch.isalpha() for ch in line):
            return line
    return None


def _normalize_date(raw: str) -> str | None:
    text = raw.strip()
    formats = (
        "%d/%m/%Y",
        "%d-%m-%Y",
        "%Y-%m-%d",
        "%Y/%m/%d",
        "%b %d %Y",
        "%b %d, %Y",
        "%B %d %Y",
        "%B %d, %Y",
    )
    for fmt in formats:
        try:
            return datetime.strptime(text, fmt).date().isoformat()
        except ValueError:
            continue
    return None


def _extract_text(text: str) -> dict:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    expense_lines = lines[:10]

    amount, currency = _extract_amount_and_currency(lines, text)

    date_match = re.search(DATE_PATTERN, text)
    vendor = _extract_vendor(lines)

    return {
        "amount": amount,
        "date": _normalize_date(date_match.group(1)) if date_match else None,
        "description": vendor,
        "vendor": vendor,
        "currency": currency,
        "expense_type": _infer_expense_type(text),
        "expense_lines": expense_lines,
    }


def extract_receipt_data(image_bytes: bytes) -> dict:
    text = pytesseract.image_to_string(preprocess(image_bytes), config="--psm 6")
    return _extract_text(text)


def extract_receipt_data_from_pdf(pdf_bytes: bytes) -> dict:
    pdf = pdfium.PdfDocument(pdf_bytes)
    if len(pdf) == 0:
        return {
            "amount": None,
            "date": None,
            "description": None,
            "vendor": None,
            "currency": None,
            "expense_type": None,
            "expense_lines": [],
        }

    page = pdf[0]
    bitmap = page.render(scale=2.0)
    pil_image = bitmap.to_pil().convert("L")
    pil_image = pil_image.filter(ImageFilter.SHARPEN)
    enhancer = ImageEnhance.Contrast(pil_image)
    pil_image = enhancer.enhance(2.0)
    text = pytesseract.image_to_string(pil_image, config="--psm 6")
    page.close()
    pdf.close()
    return _extract_text(text)
