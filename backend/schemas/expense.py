from datetime import date, datetime

from pydantic import BaseModel, ConfigDict

from backend.schemas.approval import ApprovalStepResponse, AuditLogResponse


class ExpenseCreate(BaseModel):
    amount: float
    currency: str
    category: str
    description: str
    date: date
    receipt_url: str | None = None


class ExpenseResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    employee_id: int
    amount: float
    currency: str
    amount_in_base: float
    category: str
    description: str
    date: date
    receipt_url: str | None
    status: str
    current_step_order: int
    created_at: datetime


class ExpenseDetailResponse(ExpenseResponse):
    approval_steps: list[ApprovalStepResponse]
    audit_logs: list[AuditLogResponse]
