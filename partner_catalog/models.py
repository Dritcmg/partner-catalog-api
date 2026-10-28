"""SQLite schema: constraints also protect persistence outside API validation."""

from sqlalchemy import Boolean, CheckConstraint, String, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Partner(Base):
    __tablename__ = "partners"
    __table_args__ = (
        UniqueConstraint("code", name="uq_partner_code"),
        CheckConstraint("length(code) BETWEEN 3 AND 32", name="ck_partner_code_length"),
        CheckConstraint("length(display_name) BETWEEN 3 AND 120", name="ck_partner_name_length"),
        CheckConstraint(
            "category IN ('originator', 'investor', 'servicer')", name="ck_partner_category"
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    code: Mapped[str] = mapped_column(String(32), nullable=False)
    display_name: Mapped[str] = mapped_column(String(120), nullable=False)
    category: Mapped[str] = mapped_column(String(20), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean(create_constraint=True), nullable=False)
    created_at: Mapped[str] = mapped_column(String(40), nullable=False)
