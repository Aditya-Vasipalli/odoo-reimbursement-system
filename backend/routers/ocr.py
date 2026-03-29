from fastapi import APIRouter, File, HTTPException, UploadFile

from backend.services.ocr_service import extract_receipt_data, extract_receipt_data_from_pdf


router = APIRouter(prefix="/ocr", tags=["ocr"])

MAX_FILE_SIZE = 5 * 1024 * 1024
ALLOWED_CONTENT_TYPES = {
    "image/png",
    "image/jpeg",
    "image/jpg",
    "image/webp",
    "image/heic",
    "image/heif",
    "application/pdf",
}


def _empty_ocr_result() -> dict:
    return {
        "amount": None,
        "date": None,
        "description": None,
        "vendor": None,
        "currency": None,
    }


@router.post("/scan")
async def scan_receipt(file: UploadFile = File(...)):
    if not file.content_type or file.content_type.lower() not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(status_code=400, detail="Unsupported file type")

    image_bytes = await file.read()
    if not image_bytes:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")

    if len(image_bytes) > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="File too large")

    try:
        if file.content_type == "application/pdf":
            return extract_receipt_data_from_pdf(image_bytes)
        return extract_receipt_data(image_bytes)
    except Exception:
        result = _empty_ocr_result()
        # Preserve backward compatibility with main branch payload additions.
        result["expense_type"] = None
        result["expense_lines"] = []
        return result
