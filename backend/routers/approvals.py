from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models.approval import ApprovalStep
from backend.models.expense import Expense
from backend.models.user import RoleEnum, User
from backend.security import get_current_user


router = APIRouter(prefix="/approvals", tags=["approvals"])


@router.get("/queue")
def my_approval_queue(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if current_user.role not in {RoleEnum.manager, RoleEnum.admin}:
        return []

    steps = (
        db.query(ApprovalStep)
        .join(Expense, Expense.id == ApprovalStep.expense_id)
        .join(User, User.id == Expense.employee_id)
        .filter(ApprovalStep.approver_id == current_user.id, ApprovalStep.status == "pending")
        .order_by(ApprovalStep.created_at.asc())
        .all()
    )
    return [
        {
            "expense_id": step.expense_id,
            "step_order": step.step_order,
            "status": step.status,
            "created_at": step.created_at,
            "amount": step.expense.amount,
            "currency": step.expense.currency,
            "category": step.expense.category,
            "date": step.expense.date,
            "employee_id": step.expense.employee_id,
            "employee_name": step.expense.employee.name if step.expense.employee else None,
        }
        for step in steps
    ]
