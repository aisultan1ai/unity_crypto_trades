"""create binance trades tables

Revision ID: 20260413_01
Revises:
Create Date: 2026-04-13 18:30:00
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260413_01"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "binance_subaccounts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("remark", sa.String(length=255), nullable=True),
        sa.Column("is_frozen", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("is_managed", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("futures_enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("last_archive_sync_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_incremental_sync_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("email", name="uq_binance_subaccounts_email"),
    )
    op.create_index("ix_binance_subaccounts_email", "binance_subaccounts", ["email"], unique=False)

    op.create_table(
        "binance_sync_jobs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("subaccount_id", sa.Integer(), sa.ForeignKey("binance_subaccounts.id"), nullable=False),
        sa.Column("job_type", sa.String(length=50), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="queued"),
        sa.Column("period_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("period_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("download_id", sa.String(length=128), nullable=True),
        sa.Column("download_url", sa.Text(), nullable=True),
        sa.Column("rows_loaded", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_text", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_binance_sync_jobs_subaccount_id", "binance_sync_jobs", ["subaccount_id"], unique=False)

    op.create_table(
        "futures_trades",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("subaccount_id", sa.Integer(), sa.ForeignKey("binance_subaccounts.id"), nullable=False),
        sa.Column("symbol", sa.String(length=50), nullable=False),
        sa.Column("trade_id", sa.BigInteger(), nullable=False),
        sa.Column("order_id", sa.BigInteger(), nullable=True),
        sa.Column("side", sa.String(length=10), nullable=True),
        sa.Column("position_side", sa.String(length=10), nullable=True),
        sa.Column("price", sa.Numeric(28, 10), nullable=True),
        sa.Column("qty", sa.Numeric(28, 10), nullable=True),
        sa.Column("quote_qty", sa.Numeric(28, 10), nullable=True),
        sa.Column("realized_pnl", sa.Numeric(28, 10), nullable=True),
        sa.Column("commission", sa.Numeric(28, 10), nullable=True),
        sa.Column("commission_asset", sa.String(length=20), nullable=True),
        sa.Column("is_maker", sa.Boolean(), nullable=True),
        sa.Column("trade_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source_type", sa.String(length=20), nullable=False),
        sa.Column("raw_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint(
            "subaccount_id",
            "symbol",
            "trade_id",
            name="uq_trade_sub_symbol_tradeid",
        ),
    )
    op.create_index("ix_futures_trades_subaccount_id", "futures_trades", ["subaccount_id"], unique=False)
    op.create_index("ix_futures_trades_symbol", "futures_trades", ["symbol"], unique=False)
    op.create_index("ix_futures_trades_trade_time", "futures_trades", ["trade_time"], unique=False)
    op.create_index("ix_futures_trades_symbol_trade_time", "futures_trades", ["symbol", "trade_time"], unique=False)

    op.create_table(
        "futures_symbols_registry",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("subaccount_id", sa.Integer(), sa.ForeignKey("binance_subaccounts.id"), nullable=False),
        sa.Column("symbol", sa.String(length=50), nullable=False),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("subaccount_id", "symbol", name="uq_symbol_registry_sub_symbol"),
    )
    op.create_index(
        "ix_futures_symbols_registry_subaccount_id",
        "futures_symbols_registry",
        ["subaccount_id"],
        unique=False,
    )
    op.create_index(
        "ix_futures_symbols_registry_symbol",
        "futures_symbols_registry",
        ["symbol"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_futures_symbols_registry_symbol", table_name="futures_symbols_registry")
    op.drop_index("ix_futures_symbols_registry_subaccount_id", table_name="futures_symbols_registry")
    op.drop_table("futures_symbols_registry")

    op.drop_index("ix_futures_trades_symbol_trade_time", table_name="futures_trades")
    op.drop_index("ix_futures_trades_trade_time", table_name="futures_trades")
    op.drop_index("ix_futures_trades_symbol", table_name="futures_trades")
    op.drop_index("ix_futures_trades_subaccount_id", table_name="futures_trades")
    op.drop_table("futures_trades")

    op.drop_index("ix_binance_sync_jobs_subaccount_id", table_name="binance_sync_jobs")
    op.drop_table("binance_sync_jobs")

    op.drop_index("ix_binance_subaccounts_email", table_name="binance_subaccounts")
    op.drop_table("binance_subaccounts")