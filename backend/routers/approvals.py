from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models.approval import ApprovalStep
from backend.models.user import RoleEnum, User
from backend.security import get_current_user


router = APIRouter(prefix="/approvals", tags=["approvals"])


@router.get("/queue")
def my_approval_queue(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if current_user.role not in {RoleEnum.manager, RoleEnum.admin}:
        return []

    steps = (
        db.query(ApprovalStep)
        .filter(ApprovalStep.approver_id == current_user.id, ApprovalStep.status == "pending")
        .order_by(ApprovalStep.created_at.asc())
        .all()
    )
    return [{"expense_id": step.expense_id, "step_order": step.step_order} for step in steps]
