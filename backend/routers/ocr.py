from fastapi import APIRouter, File, HTTPException, UploadFile

from backend.services.ocr_service import extract_receipt_data


router = APIRouter(prefix="/ocr", tags=["ocr"])

MAX_FILE_SIZE = 5 * 1024 * 1024


@router.post("/scan")
async def scan_receipt(file: UploadFile = File(...)):
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Only image files are supported")

    image_bytes = await file.read()
    if len(image_bytes) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="File too large")

    try:
        return extract_receipt_data(image_bytes)
    except Exception:
        return {
            "amount": None,
            "date": None,
            "description": None,
            "vendor": None,
            "currency": None,
        }
