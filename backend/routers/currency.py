from fastapi import APIRouter, HTTPException, Query

from backend.services.currency import convert_amount, get_countries


router = APIRouter(prefix="/currency", tags=["currency"])


@router.get("/countries")
def countries():
    return get_countries()


@router.get("/convert")
def convert(from_currency: str = Query(alias="from"), to: str = Query(...), amount: float = Query(...)):
    converted, rate = convert_amount(amount, from_currency, to)
    if converted is None:
        raise HTTPException(status_code=503, detail="Currency conversion unavailable")
    return {"converted_amount": converted, "rate": rate}
