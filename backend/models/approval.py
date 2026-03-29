from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.database import Base


class ApprovalRule(Base):
    __tablename__ = "approval_rules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    threshold_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    specific_approver_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    is_hybrid: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_manager_first: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    company = relationship("Company", back_populates="approval_rules")
    steps = relationship("ApprovalRuleStep", back_populates="rule", cascade="all, delete-orphan")


class ApprovalStep(Base):
    __tablename__ = "approval_steps"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    expense_id: Mapped[int] = mapped_column(ForeignKey("expenses.id"), nullable=False)
    rule_id: Mapped[int | None] = mapped_column(ForeignKey("approval_rules.id"), nullable=True)
    approver_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    step_order: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="pending", nullable=False)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    acted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    expense = relationship("Expense", back_populates="approval_steps")
    approver = relationship("User", back_populates="approval_steps")


class ApprovalRuleStep(Base):
    __tablename__ = "approval_rule_steps"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    rule_id: Mapped[int] = mapped_column(ForeignKey("approval_rules.id"), nullable=False)
    approver_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    step_order: Mapped[int] = mapped_column(Integer, nullable=False)

    rule = relationship("ApprovalRule", back_populates="steps")
