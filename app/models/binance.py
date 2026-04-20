from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    BigInteger,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Index,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class BinanceSubAccount(Base):
    __tablename__ = "binance_subaccounts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    remark: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_frozen: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_managed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    futures_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    last_archive_sync_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_incremental_sync_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    trades: Mapped[list["FuturesTrade"]] = relationship(back_populates="subaccount")


class BinanceSyncJob(Base):
    __tablename__ = "binance_sync_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    subaccount_id: Mapped[int] = mapped_column(ForeignKey("binance_subaccounts.id"), index=True)
    job_type: Mapped[str] = mapped_column(String(50))
    status: Mapped[str] = mapped_column(String(30), default="queued")

    period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    period_end: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    download_id: Mapped[str | None] = mapped_column(String(128))
    download_url: Mapped[str | None] = mapped_column(Text)
    rows_loaded: Mapped[int] = mapped_column(Integer, default=0)
    error_text: Mapped[str | None] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class FuturesTrade(Base):
    __tablename__ = "futures_trades"
    __table_args__ = (
        UniqueConstraint("subaccount_id", "symbol", "trade_id", name="uq_trade_sub_symbol_tradeid"),
        Index("ix_futures_trades_time", "trade_time"),
        Index("ix_futures_trades_symbol_time", "symbol", "trade_time"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    subaccount_id: Mapped[int] = mapped_column(ForeignKey("binance_subaccounts.id"), index=True)

    symbol: Mapped[str] = mapped_column(String(50), index=True)
    trade_id: Mapped[int] = mapped_column(BigInteger)
    order_id: Mapped[int | None] = mapped_column(BigInteger)

    side: Mapped[str | None] = mapped_column(String(10))
    position_side: Mapped[str | None] = mapped_column(String(10))

    price: Mapped[Decimal | None] = mapped_column(Numeric(28, 10))
    qty: Mapped[Decimal | None] = mapped_column(Numeric(28, 10))
    quote_qty: Mapped[Decimal | None] = mapped_column(Numeric(28, 10))
    realized_pnl: Mapped[Decimal | None] = mapped_column(Numeric(28, 10))
    commission: Mapped[Decimal | None] = mapped_column(Numeric(28, 10))
    commission_asset: Mapped[str | None] = mapped_column(String(20))

    is_maker: Mapped[bool | None] = mapped_column(Boolean)
    trade_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)

    source_type: Mapped[str] = mapped_column(String(20))
    raw_payload: Mapped[dict | None] = mapped_column(JSONB)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    subaccount: Mapped["BinanceSubAccount"] = relationship(back_populates="trades")


class FuturesSymbolRegistry(Base):
    __tablename__ = "futures_symbols_registry"
    __table_args__ = (
        UniqueConstraint("subaccount_id", "symbol", name="uq_symbol_registry_sub_symbol"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    subaccount_id: Mapped[int] = mapped_column(ForeignKey("binance_subaccounts.id"), index=True)
    symbol: Mapped[str] = mapped_column(String(50), index=True)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))