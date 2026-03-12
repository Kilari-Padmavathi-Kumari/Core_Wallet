from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, Index, Numeric, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from sqlalchemy import Identity


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    user_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    password_hash: Mapped[str] = mapped_column(String(256), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    wallet: Mapped["Wallet"] = relationship(back_populates="user", uselist=False)


class Wallet(Base):
    __tablename__ = "wallets"
    __table_args__ = (
        CheckConstraint("balance >= 0", name="ck_wallets_balance_nonnegative"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    user_id: Mapped[str] = mapped_column(
        String(128),
        ForeignKey("users.user_id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    balance: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False, server_default="0")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped["User"] = relationship(back_populates="wallet")
    ledger_entries: Mapped[list["LedgerEntry"]] = relationship(back_populates="wallet")


class LedgerEntry(Base):
    __tablename__ = "ledger_entries"
    __table_args__ = (
        CheckConstraint("entry_type IN ('credit', 'debit')", name="ck_ledger_entry_type"),
        CheckConstraint("amount > 0", name="ck_ledger_amount_positive"),
        CheckConstraint("balance_after >= 0", name="ck_ledger_balance_after_nonnegative"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    wallet_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("wallets.id", ondelete="CASCADE"),
        nullable=False,
    )
    entry_type: Mapped[str] = mapped_column(String(16), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    balance_after: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    wallet: Mapped["Wallet"] = relationship(back_populates="ledger_entries")


Index("idx_ledger_wallet_created_at", LedgerEntry.wallet_id, LedgerEntry.created_at.desc())
