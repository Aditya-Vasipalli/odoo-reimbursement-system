from fastapi import APIRouter, HTTPException, Query

from backend.services.currency import convert_amount, get_countries


router = APIRouter(prefix="/currency", tags=["currency"])


@router.get("/countries")
def countries():
    result = get_countries()
    if not result:
        raise HTTPException(status_code=502, detail="Unable to fetch country/currency data")
    return result


@router.get("/convert")
def convert(
    from_currency: str = Query(..., alias="from", min_length=3, max_length=3),
    to: str = Query(..., min_length=3, max_length=3),
    amount: float = Query(..., gt=0),
):
    converted, rate = convert_amount(amount, from_currency, to)
    if converted is None:
        raise HTTPException(status_code=502, detail="Currency conversion unavailable")
    return {"converted_amount": converted, "rate": rate}
