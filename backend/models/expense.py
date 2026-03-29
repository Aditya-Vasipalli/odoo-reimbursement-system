import enum
from datetime import date, datetime

from sqlalchemy import Date, DateTime, Enum, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.database import Base


class ExpenseStatus(str, enum.Enum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"


class AuditAction(str, enum.Enum):
    submitted = "submitted"
    approved = "approved"
    rejected = "rejected"
    overridden = "overridden"


class Expense(Base):
    __tablename__ = "expenses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    amount: Mapped[float] = mapped_column(Float, nullable=False)
    currency: Mapped[str] = mapped_column(String(8), nullable=False)
    amount_in_base: Mapped[float] = mapped_column(Float, nullable=False)
    category: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    receipt_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    status: Mapped[ExpenseStatus] = mapped_column(Enum(ExpenseStatus), default=ExpenseStatus.pending, nullable=False)
    current_step_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    employee = relationship("User", back_populates="expenses")
    approval_steps = relationship("ApprovalStep", back_populates="expense", cascade="all, delete-orphan")
    audit_logs = relationship("ExpenseAuditLog", back_populates="expense", cascade="all, delete-orphan")


class ExpenseAuditLog(Base):
    __tablename__ = "expense_audit_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    expense_id: Mapped[int] = mapped_column(ForeignKey("expenses.id"), nullable=False)
    actor_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    action: Mapped[AuditAction] = mapped_column(Enum(AuditAction), nullable=False)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    expense = relationship("Expense", back_populates="audit_logs")
    actor = relationship("User", back_populates="acted_audit_logs")
