from fastapi import APIRouter, File, HTTPException, UploadFile

from backend.services.ocr_service import extract_receipt_data, extract_receipt_data_from_pdf


router = APIRouter(prefix="/ocr", tags=["ocr"])

MAX_FILE_SIZE = 5 * 1024 * 1024


@router.post("/scan")
async def scan_receipt(file: UploadFile = File(...)):
    allowed = {"application/pdf"}
    if not file.content_type or (not file.content_type.startswith("image/") and file.content_type not in allowed):
        raise HTTPException(status_code=400, detail="Only image or PDF files are supported")

    image_bytes = await file.read()
    if len(image_bytes) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="File too large")

    try:
        if file.content_type == "application/pdf":
            return extract_receipt_data_from_pdf(image_bytes)
        return extract_receipt_data(image_bytes)
    except Exception:
        return {
            "amount": None,
            "date": None,
            "description": None,
            "vendor": None,
            "currency": None,
            "expense_type": None,
            "expense_lines": [],
        }
