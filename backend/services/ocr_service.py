import io
import re

from PIL import Image, ImageEnhance, ImageFilter
import pytesseract


AMOUNT_PATTERNS = [
    r"(?:total|amount|amt)\s*[:\-]?\s*([\$\u20b9\u20ac\u00a3]?\s?\d+[\.,]?\d*)",
    r"([\$\u20b9\u20ac\u00a3]\s?\d+[\.,]?\d*)",
]
DATE_PATTERN = r"(\d{2}[/-]\d{2}[/-]\d{4}|\d{4}-\d{2}-\d{2}|[A-Za-z]{3,9}\s+\d{1,2},?\s+\d{4})"


def preprocess(image_bytes: bytes) -> Image.Image:
    img = Image.open(io.BytesIO(image_bytes)).convert("L")
    img = img.filter(ImageFilter.SHARPEN)
    enhancer = ImageEnhance.Contrast(img)
    return enhancer.enhance(2.0)


def extract_receipt_data(image_bytes: bytes) -> dict:
    text = pytesseract.image_to_string(preprocess(image_bytes), config="--psm 6")
    lines = [line.strip() for line in text.splitlines() if line.strip()]

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
    }
