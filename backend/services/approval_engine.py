from datetime import datetime

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from backend.models.approval import ApprovalRule, ApprovalRuleStep, ApprovalStep
from backend.models.expense import AuditAction, Expense, ExpenseAuditLog, ExpenseStatus
from backend.models.user import User


def get_applicable_rule(db: Session, expense: Expense) -> ApprovalRule | None:
    return (
        db.query(ApprovalRule)
        .filter(ApprovalRule.company_id == expense.employee.company_id)
        .order_by(ApprovalRule.created_at.desc())
        .first()
    )


def initialize_steps(db: Session, expense: Expense, rule: ApprovalRule | None) -> None:
    if not rule:
        expense.status = ExpenseStatus.approved
        return

    rule_steps = (
        db.query(ApprovalRuleStep)
        .filter(ApprovalRuleStep.rule_id == rule.id)
        .order_by(ApprovalRuleStep.step_order.asc())
        .all()
    )

    created_orders = set()

    if rule.is_manager_first and expense.employee.manager_id:
        manager_step = ApprovalStep(
            expense_id=expense.id,
            rule_id=rule.id,
            approver_id=expense.employee.manager_id,
            step_order=0,
            status="pending",
        )
        db.add(manager_step)
        created_orders.add(0)

    for step in rule_steps:
        order = step.step_order
        while order in created_orders:
            order += 1
        db.add(
            ApprovalStep(
                expense_id=expense.id,
                rule_id=rule.id,
                approver_id=step.approver_id,
                step_order=order,
                status="pending",
            )
        )
        created_orders.add(order)

    expense.current_step_order = min(created_orders) if created_orders else 0


def evaluate_condition(rule: ApprovalRule, steps: list[ApprovalStep]) -> bool:
    if not steps:
        return True

    approved_steps = [step for step in steps if step.status == "approved"]

    if rule.specific_approver_id and any(step.approver_id == rule.specific_approver_id for step in approved_steps):
        return True

    if rule.threshold_pct is not None:
        approval_ratio = (len(approved_steps) / len(steps)) * 100
        if approval_ratio >= rule.threshold_pct:
            return True

    if not rule.is_hybrid and rule.threshold_pct is None and rule.specific_approver_id is None:
        return len(approved_steps) == len(steps)

    if rule.is_hybrid:
        if rule.specific_approver_id and any(step.approver_id == rule.specific_approver_id for step in approved_steps):
            return True
        if rule.threshold_pct is not None:
            approval_ratio = (len(approved_steps) / len(steps)) * 100
            return approval_ratio >= rule.threshold_pct

    return False


def advance_expense(db: Session, expense: Expense, actor: User, action: str, comment: str | None) -> Expense:
    if expense.status != ExpenseStatus.pending:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Expense is already resolved")

    steps = sorted(expense.approval_steps, key=lambda item: item.step_order)
    current_step = next((step for step in steps if step.step_order == expense.current_step_order and step.status == "pending"), None)

    if current_step is None:
        expense.status = ExpenseStatus.approved
        return expense

    if current_step.approver_id != actor.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your approval step")

    now = datetime.utcnow()

    if action == "rejected":
        current_step.status = "rejected"
        current_step.comment = comment
        current_step.acted_at = now
        expense.status = ExpenseStatus.rejected
        db.add(
            ExpenseAuditLog(
                expense_id=expense.id,
                actor_id=actor.id,
                action=AuditAction.rejected,
                comment=comment,
            )
        )
        return expense

    if action != "approved":
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Action must be approved or rejected")

    current_step.status = "approved"
    current_step.comment = comment
    current_step.acted_at = now

    rule = db.query(ApprovalRule).filter(ApprovalRule.id == current_step.rule_id).first() if current_step.rule_id else None
    if rule and evaluate_condition(rule, steps):
        expense.status = ExpenseStatus.approved
    else:
        next_step = next((step for step in steps if step.step_order > current_step.step_order and step.status == "pending"), None)
        if next_step:
            expense.current_step_order = next_step.step_order
        else:
            expense.status = ExpenseStatus.approved

    db.add(
        ExpenseAuditLog(
            expense_id=expense.id,
            actor_id=actor.id,
            action=AuditAction.approved,
            comment=comment,
        )
    )
    return expense
