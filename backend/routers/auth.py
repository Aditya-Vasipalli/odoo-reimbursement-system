from fastapi import APIRouter, Depends, HTTPException, status
import httpx
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models.user import Company, RoleEnum, User
from backend.schemas.user import MeResponse, TokenResponse, UserCreate, UserLogin, UserResponse
from backend.security import create_access_token, get_current_user, hash_password, verify_password


router = APIRouter(prefix="/auth", tags=["auth"])


def _currency_from_country(country_code: str) -> str:
    code = country_code.upper().strip()
    try:
        response = httpx.get(f"https://restcountries.com/v3.1/alpha/{code}?fields=currencies", timeout=10.0)
        response.raise_for_status()
        payload = response.json()
        item = payload[0] if isinstance(payload, list) and payload else payload
        currencies = (item or {}).get("currencies") or {}
        if currencies:
            return next(iter(currencies.keys()))
    except Exception:
        pass

    fallback = {
        "IN": "INR",
        "US": "USD",
        "GB": "GBP",
        "FR": "EUR",
        "DE": "EUR",
        "IT": "EUR",
        "ES": "EUR",
    }
    if code in fallback:
        return fallback[code]

    return "USD"


@router.post("/signup", response_model=TokenResponse)
def signup(payload: UserCreate, db: Session = Depends(get_db)):
    existing = db.query(User).filter(User.email == payload.email).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already exists")

    company = Company(
        name=payload.company_name or f"{payload.name}'s Company",
        country_code=payload.country_code.upper(),
        currency_code=_currency_from_country(payload.country_code),
    )
    db.add(company)
    db.flush()

    user = User(
        company_id=company.id,
        name=payload.name,
        email=payload.email,
        password_hash=hash_password(payload.password),
        role=RoleEnum.admin,
        manager_id=None,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    db.refresh(company)

    token = create_access_token(user.id, user.role.value, user.company_id)
    return TokenResponse(
        token=token,
        user=UserResponse.model_validate(user),
        company=company,
    )


@router.post("/login", response_model=TokenResponse)
def login(payload: UserLogin, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == payload.email).first()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    company = db.query(Company).filter(Company.id == user.company_id).first()
    token = create_access_token(user.id, user.role.value, user.company_id)
    return TokenResponse(
        token=token,
        user=UserResponse.model_validate(user),
        company=company,
    )


@router.get("/me", response_model=MeResponse)
def me(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    company = db.query(Company).filter(Company.id == current_user.company_id).first()
    return MeResponse(
        user=UserResponse.model_validate(current_user),
        company=company,
        role=current_user.role.value,
    )
