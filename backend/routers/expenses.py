from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models.expense import AuditAction, Expense, ExpenseAuditLog, ExpenseStatus
from backend.models.user import RoleEnum, User
from backend.schemas.approval import ApprovalAction
from backend.schemas.expense import ExpenseCreate, ExpenseDetailResponse, ExpenseResponse
from backend.security import get_current_user
from backend.services.approval_engine import advance_expense, get_applicable_rule, initialize_steps
from backend.services.currency import convert_amount


router = APIRouter(prefix="/expenses", tags=["expenses"])


@router.post("", response_model=ExpenseResponse)
def create_expense(payload: ExpenseCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    base_currency = current_user.company.currency_code
    converted, _ = convert_amount(payload.amount, payload.currency, base_currency)
    amount_in_base = converted if converted is not None else payload.amount

    expense = Expense(
        employee_id=current_user.id,
        amount=payload.amount,
        currency=payload.currency.upper(),
        amount_in_base=amount_in_base,
        category=payload.category,
        description=payload.description,
        date=payload.date,
        receipt_url=payload.receipt_url,
        status=ExpenseStatus.pending,
        current_step_order=0,
    )
    db.add(expense)
    db.flush()
    db.refresh(expense)

    rule = get_applicable_rule(db, expense)
    initialize_steps(db, expense, rule)
    db.add(
        ExpenseAuditLog(
            expense_id=expense.id,
            actor_id=current_user.id,
            action=AuditAction.submitted,
            comment="Expense submitted",
        )
    )

    db.commit()
    db.refresh(expense)
    return ExpenseResponse.model_validate(expense)


@router.get("/mine", response_model=list[ExpenseResponse])
def get_my_expenses(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    expenses = (
        db.query(Expense)
        .filter(Expense.employee_id == current_user.id)
        .order_by(Expense.created_at.desc())
        .all()
    )
    return [ExpenseResponse.model_validate(item) for item in expenses]


@router.get("/team", response_model=list[ExpenseResponse])
def get_team_expenses(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if current_user.role not in {RoleEnum.manager, RoleEnum.admin}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Manager/Admin role required")

    if current_user.role == RoleEnum.admin:
        expenses = (
            db.query(Expense)
            .join(User, User.id == Expense.employee_id)
            .filter(User.company_id == current_user.company_id)
            .order_by(Expense.created_at.desc())
            .all()
        )
    else:
        report_ids = [report.id for report in current_user.reports]
        expenses = (
            db.query(Expense)
            .filter(Expense.employee_id.in_(report_ids))
            .order_by(Expense.created_at.desc())
            .all()
            if report_ids
            else []
        )

    return [ExpenseResponse.model_validate(item) for item in expenses]


@router.get("/all", response_model=list[ExpenseResponse])
def get_all_expenses(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if current_user.role != RoleEnum.admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin role required")

    expenses = (
        db.query(Expense)
        .join(User, User.id == Expense.employee_id)
        .filter(User.company_id == current_user.company_id)
        .order_by(Expense.created_at.desc())
        .all()
    )
    return [ExpenseResponse.model_validate(item) for item in expenses]


@router.get("/{expense_id}", response_model=ExpenseDetailResponse)
def get_expense(expense_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    expense = db.query(Expense).filter(Expense.id == expense_id).first()
    if not expense:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Expense not found")

    is_owner = expense.employee_id == current_user.id
    is_manager_of_owner = expense.employee.manager_id == current_user.id if expense.employee else False
    is_admin = current_user.role == RoleEnum.admin and expense.employee.company_id == current_user.company_id
    if not (is_owner or is_manager_of_owner or is_admin):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed to view this expense")

    return ExpenseDetailResponse.model_validate(expense)


@router.patch("/{expense_id}/approve", response_model=ExpenseResponse)
def approve_expense(
    expense_id: int,
    payload: ApprovalAction,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    expense = db.query(Expense).filter(Expense.id == expense_id).first()
    if not expense:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Expense not found")

    action = payload.action.lower().strip()
    updated = advance_expense(db, expense, current_user, action, payload.comment)
    db.commit()
    db.refresh(updated)
    return ExpenseResponse.model_validate(updated)


@router.delete("/{expense_id}")
def delete_expense(expense_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    expense = db.query(Expense).filter(Expense.id == expense_id).first()
    if not expense:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Expense not found")

    if expense.employee_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only owner can delete")

    if expense.status != ExpenseStatus.pending:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only pending expenses can be deleted")

    db.delete(expense)
    db.commit()
    return {"ok": True}
