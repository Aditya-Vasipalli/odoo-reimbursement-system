from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models.approval import ApprovalRule, ApprovalRuleStep
from backend.models.expense import AuditAction, Expense, ExpenseAuditLog, ExpenseStatus
from backend.models.user import RoleEnum, User
from backend.schemas.approval import AdminOverrideAction, ApprovalRuleCreate, ApprovalRuleResponse
from backend.schemas.user import AdminUserCreate, AdminUserUpdate, UserResponse
from backend.security import hash_password, require_admin


router = APIRouter(prefix="/admin", tags=["admin"])


@router.post("/users", response_model=UserResponse)
def create_user(payload: AdminUserCreate, db: Session = Depends(get_db), current_user: User = Depends(require_admin)):
    if payload.role not in {RoleEnum.admin.value, RoleEnum.manager.value, RoleEnum.employee.value}:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid role")

    if db.query(User).filter(User.email == payload.email).first():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already exists")

    user = User(
        company_id=current_user.company_id,
        name=payload.name,
        email=payload.email,
        password_hash=hash_password(payload.password),
        role=RoleEnum(payload.role),
        manager_id=payload.manager_id,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return UserResponse.model_validate(user)


@router.patch("/users/{user_id}", response_model=UserResponse)
def update_user(
    user_id: int,
    payload: AdminUserUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    user = db.query(User).filter(User.id == user_id, User.company_id == current_user.company_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    if payload.role:
        if payload.role not in {RoleEnum.admin.value, RoleEnum.manager.value, RoleEnum.employee.value}:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid role")
        user.role = RoleEnum(payload.role)

    if "manager_id" in payload.model_fields_set:
        user.manager_id = payload.manager_id

    db.commit()
    db.refresh(user)
    return UserResponse.model_validate(user)


@router.get("/users", response_model=list[UserResponse])
def get_users(db: Session = Depends(get_db), current_user: User = Depends(require_admin)):
    users = db.query(User).filter(User.company_id == current_user.company_id).order_by(User.created_at.asc()).all()
    return [UserResponse.model_validate(item) for item in users]


@router.post("/approval-rules", response_model=ApprovalRuleResponse)
def create_approval_rule(
    payload: ApprovalRuleCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    rule = ApprovalRule(
        company_id=current_user.company_id,
        name=payload.name,
        threshold_pct=payload.threshold,
        specific_approver_id=payload.specific_approver_id,
        is_hybrid=payload.is_hybrid,
        is_manager_first=payload.is_manager_first,
    )
    db.add(rule)
    db.flush()

    for step in payload.steps:
        db.add(
            ApprovalRuleStep(
                rule_id=rule.id,
                approver_id=step.approver_id,
                step_order=step.order,
            )
        )

    db.commit()
    db.refresh(rule)
    return ApprovalRuleResponse.model_validate(rule)


@router.get("/approval-rules", response_model=list[ApprovalRuleResponse])
def get_approval_rules(db: Session = Depends(get_db), current_user: User = Depends(require_admin)):
    rules = (
        db.query(ApprovalRule)
        .filter(ApprovalRule.company_id == current_user.company_id)
        .order_by(ApprovalRule.created_at.desc())
        .all()
    )
    return [ApprovalRuleResponse.model_validate(item) for item in rules]


@router.post("/expenses/{expense_id}/override")
def override_expense(
    expense_id: int,
    payload: AdminOverrideAction,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    expense = (
        db.query(Expense)
        .join(User, User.id == Expense.employee_id)
        .filter(Expense.id == expense_id, User.company_id == current_user.company_id)
        .first()
    )
    if not expense:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Expense not found")

    action = payload.action.lower().strip()
    if action == "approved":
        expense.status = ExpenseStatus.approved
    elif action == "rejected":
        expense.status = ExpenseStatus.rejected
    else:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Action must be approved or rejected")

    db.add(
        ExpenseAuditLog(
            expense_id=expense.id,
            actor_id=current_user.id,
            action=AuditAction.overridden,
            comment=payload.reason,
        )
    )
    db.commit()
    return {"ok": True, "status": expense.status.value}


@router.get("/analytics")
def get_analytics(db: Session = Depends(get_db), current_user: User = Depends(require_admin)):
    base_query = db.query(Expense).join(User, User.id == Expense.employee_id).filter(User.company_id == current_user.company_id)

    total_pending = base_query.filter(Expense.status == ExpenseStatus.pending).count()
    total_approved = base_query.filter(Expense.status == ExpenseStatus.approved).count()
    total_rejected = base_query.filter(Expense.status == ExpenseStatus.rejected).count()

    by_category_rows = (
        db.query(Expense.category, func.sum(Expense.amount_in_base))
        .join(User, User.id == Expense.employee_id)
        .filter(User.company_id == current_user.company_id)
        .group_by(Expense.category)
        .all()
    )
    by_category = [{"category": row[0], "total": float(row[1] or 0)} for row in by_category_rows]

    top_spenders_rows = (
        db.query(User.name, func.sum(Expense.amount_in_base).label("total"))
        .join(Expense, Expense.employee_id == User.id)
        .filter(User.company_id == current_user.company_id)
        .group_by(User.name)
        .order_by(func.sum(Expense.amount_in_base).desc())
        .limit(5)
        .all()
    )
    top_spenders = [{"name": row[0], "total": float(row[1] or 0)} for row in top_spenders_rows]

    return {
        "total_pending": total_pending,
        "total_approved": total_approved,
        "total_rejected": total_rejected,
        "by_category": by_category,
        "top_spenders": top_spenders,
    }
