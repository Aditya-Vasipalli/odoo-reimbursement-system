import io
import re

from PIL import Image, ImageEnhance, ImageFilter
import pypdfium2 as pdfium
import pytesseract


AMOUNT_PATTERNS = [
    r"(?:total|amount|amt)\s*[:\-]?\s*([\$\u20b9\u20ac\u00a3]?\s?\d+[\.,]?\d*)",
    r"([\$\u20b9\u20ac\u00a3]\s?\d+[\.,]?\d*)",
]
DATE_PATTERN = r"(\d{2}[/-]\d{2}[/-]\d{4}|\d{4}-\d{2}-\d{2}|[A-Za-z]{3,9}\s+\d{1,2},?\s+\d{4})"


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
    return enhancer.enhance(2.0)


def _extract_text(text: str) -> dict:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    expense_lines = lines[:10]

    amount = None
    for pattern in AMOUNT_PATTERNS:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            raw_amount = match.group(1)
            amount = re.sub(r"[^\d\.]", "", raw_amount)
            break

    date_match = re.search(DATE_PATTERN, text)
    currency = None
    if "$" in text:
        currency = "USD"
    elif "\u20b9" in text or "Rs" in text or "INR" in text:
        currency = "INR"
    elif "\u20ac" in text:
        currency = "EUR"
    elif "\u00a3" in text:
        currency = "GBP"

    return {
        "amount": float(amount) if amount else None,
        "date": date_match.group(1) if date_match else None,
        "description": lines[0] if lines else None,
        "vendor": lines[0] if lines else None,
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
