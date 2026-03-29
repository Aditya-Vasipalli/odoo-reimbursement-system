from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr


class CompanyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    country_code: str
    currency_code: str
    created_at: datetime


class UserCreate(BaseModel):
    name: str
    email: EmailStr
    password: str
    country_code: str
    company_name: str | None = None


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    company_id: int
    name: str
    email: EmailStr
    role: str
    manager_id: int | None
    created_at: datetime


class TokenResponse(BaseModel):
    token: str
    user: UserResponse
    company: CompanyResponse


class MeResponse(BaseModel):
    user: UserResponse
    company: CompanyResponse
    role: str


class AdminUserCreate(BaseModel):
    name: str
    email: EmailStr
    password: str
    role: str
    manager_id: int | None = None


class AdminUserUpdate(BaseModel):
    role: str | None = None
    manager_id: int | None = None
