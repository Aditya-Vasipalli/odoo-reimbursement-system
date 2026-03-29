from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ApprovalRuleStepCreate(BaseModel):
    approver_id: int
    order: int


class ApprovalRuleCreate(BaseModel):
    name: str
    threshold: float | None = None
    specific_approver_id: int | None = None
    is_hybrid: bool = False
    is_manager_first: bool = False
    steps: list[ApprovalRuleStepCreate] = []


class ApprovalRuleStepResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    approver_id: int
    step_order: int


class ApprovalRuleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    company_id: int
    name: str
    threshold_pct: float | None
    specific_approver_id: int | None
    is_hybrid: bool
    is_manager_first: bool
    created_at: datetime
    steps: list[ApprovalRuleStepResponse]


class ApprovalAction(BaseModel):
    action: str
    comment: str | None = None


class AdminOverrideAction(BaseModel):
    action: str
    reason: str


class ApprovalStepResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    approver_id: int
    step_order: int
    status: str
    comment: str | None
    acted_at: datetime | None


class AuditLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    actor_id: int
    action: str
    comment: str | None
    created_at: datetime
