from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_db
from app.integrations.binance.client import BinanceSignedClient
from app.integrations.binance.service import (
    BinanceClientFactory,
    create_sync_job,
    incremental_sync_symbol,
    run_archive_backfill,
    sync_subaccounts,
)
from app.models.binance import BinanceSubAccount, BinanceSyncJob, FuturesTrade
from app.schemas.binance import ArchiveBackfillRequest, IncrementalSyncRequest
from io import BytesIO
from fastapi.responses import StreamingResponse
from openpyxl import Workbook

router = APIRouter(prefix="/api/binance", tags=["binance-trades"])


def get_client_factory() -> BinanceClientFactory:
    settings = get_settings()

    master_client = BinanceSignedClient(
        api_key=settings.binance_master_api_key,
        api_secret=settings.binance_master_api_secret,
        spot_base_url=settings.binance_spot_base_url,
        futures_base_url=settings.binance_futures_base_url,
        recv_window=settings.binance_recv_window,
    )

    return BinanceClientFactory(
        master_client=master_client,
        subaccount_keys=settings.subaccount_keys,
        spot_base_url=settings.binance_spot_base_url,
        futures_base_url=settings.binance_futures_base_url,
        recv_window=settings.binance_recv_window,
    )


@router.post("/subaccounts/sync")
def sync_subaccounts_endpoint(
    db: Session = Depends(get_db),
    factory: BinanceClientFactory = Depends(get_client_factory),
):
    count = sync_subaccounts(db, factory.master_client)
    return {"updated": count}


@router.get("/subaccounts")
def list_subaccounts(db: Session = Depends(get_db)):
    rows = db.scalars(select(BinanceSubAccount).order_by(BinanceSubAccount.email)).all()
    return [
        {
            "id": x.id,
            "email": x.email,
            "remark": x.remark,
            "is_frozen": x.is_frozen,
            "is_managed": x.is_managed,
            "last_archive_sync_at": x.last_archive_sync_at,
            "last_incremental_sync_at": x.last_incremental_sync_at,
        }
        for x in rows
    ]


@router.post("/archive-backfill")
def archive_backfill_endpoint(
    payload: ArchiveBackfillRequest,
    db: Session = Depends(get_db),
    factory: BinanceClientFactory = Depends(get_client_factory),
):
    sub = db.scalar(select(BinanceSubAccount).where(BinanceSubAccount.email == payload.subaccount_email))
    if not sub:
        raise HTTPException(status_code=404, detail="Subaccount not found")

    job = create_sync_job(
        db=db,
        subaccount_id=sub.id,
        job_type="archive_backfill",
        period_start=payload.period_start,
        period_end=payload.period_end,
    )

    result = run_archive_backfill(db, factory, job.id)
    return result


@router.post("/incremental-sync")
def incremental_sync_endpoint(
    payload: IncrementalSyncRequest,
    db: Session = Depends(get_db),
    factory: BinanceClientFactory = Depends(get_client_factory),
):
    sub = db.scalar(select(BinanceSubAccount).where(BinanceSubAccount.email == payload.subaccount_email))
    if not sub:
        raise HTTPException(status_code=404, detail="Subaccount not found")

    start_ms = int(payload.period_start.timestamp() * 1000)
    end_ms = int(payload.period_end.timestamp() * 1000)

    return incremental_sync_symbol(
        db=db,
        client_factory=factory,
        subaccount_id=sub.id,
        symbol=payload.symbol.upper(),
        start_ms=start_ms,
        end_ms=end_ms,
    )


@router.get("/sync-jobs")
def list_sync_jobs(db: Session = Depends(get_db)):
    rows = db.scalars(
        select(BinanceSyncJob).order_by(BinanceSyncJob.created_at.desc()).limit(50)
    ).all()

    return [
        {
            "id": x.id,
            "subaccount_id": x.subaccount_id,
            "job_type": x.job_type,
            "status": x.status,
            "period_start": x.period_start,
            "period_end": x.period_end,
            "rows_loaded": x.rows_loaded,
            "download_id": x.download_id,
            "download_url": x.download_url,
            "error_text": x.error_text,
        }
        for x in rows
    ]


@router.get("/trades")
def list_trades(
    db: Session = Depends(get_db),
    subaccount_email: str | None = None,
    symbol: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    limit: int = Query(default=100, le=1000),
):
    stmt = select(FuturesTrade, BinanceSubAccount).join(
        BinanceSubAccount,
        BinanceSubAccount.id == FuturesTrade.subaccount_id,
    )

    if subaccount_email:
        stmt = stmt.where(BinanceSubAccount.email == subaccount_email)
    if symbol:
        stmt = stmt.where(FuturesTrade.symbol == symbol.upper())
    if date_from:
        stmt = stmt.where(FuturesTrade.trade_time >= date_from)
    if date_to:
        stmt = stmt.where(FuturesTrade.trade_time <= date_to)

    stmt = stmt.order_by(FuturesTrade.trade_time.desc()).limit(limit)

    rows = db.execute(stmt).all()

    return [
        {
            "subaccount_email": sub.email,
            "symbol": trade.symbol,
            "trade_id": trade.trade_id,
            "order_id": trade.order_id,
            "side": trade.side,
            "position_side": trade.position_side,
            "price": str(trade.price) if trade.price is not None else None,
            "qty": str(trade.qty) if trade.qty is not None else None,
            "quote_qty": str(trade.quote_qty) if trade.quote_qty is not None else None,
            "realized_pnl": str(trade.realized_pnl) if trade.realized_pnl is not None else None,
            "commission": str(trade.commission) if trade.commission is not None else None,
            "commission_asset": trade.commission_asset,
            "is_maker": trade.is_maker,
            "trade_time": trade.trade_time,
            "source_type": trade.source_type,
        }
        for trade, sub in rows
    ]
@router.get("/trades/export")
def export_trades_to_excel(
    db: Session = Depends(get_db),
    subaccount_email: str | None = None,
    symbol: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
):
    stmt = select(FuturesTrade, BinanceSubAccount).join(
        BinanceSubAccount,
        BinanceSubAccount.id == FuturesTrade.subaccount_id,
    )

    if subaccount_email:
        stmt = stmt.where(BinanceSubAccount.email == subaccount_email)
    if symbol:
        stmt = stmt.where(FuturesTrade.symbol == symbol.upper())
    if date_from:
        stmt = stmt.where(FuturesTrade.trade_time >= date_from)
    if date_to:
        stmt = stmt.where(FuturesTrade.trade_time <= date_to)

    stmt = stmt.order_by(FuturesTrade.trade_time.desc())

    rows = db.execute(stmt).all()

    wb = Workbook()
    ws = wb.active
    ws.title = "Trades"

    headers = [
        "Time",
        "Subaccount",
        "Symbol",
        "Trade ID",
        "Order ID",
        "Side",
        "Position Side",
        "Qty",
        "Price",
        "Quote Qty",
        "Realized PnL",
        "Commission",
        "Commission Asset",
        "Maker",
        "Source Type",
    ]
    ws.append(headers)

    for trade, sub in rows:
        ws.append([
            trade.trade_time.isoformat() if trade.trade_time else "",
            sub.email,
            trade.symbol,
            trade.trade_id,
            trade.order_id,
            trade.side,
            trade.position_side,
            float(trade.qty) if trade.qty is not None else None,
            float(trade.price) if trade.price is not None else None,
            float(trade.quote_qty) if trade.quote_qty is not None else None,
            float(trade.realized_pnl) if trade.realized_pnl is not None else None,
            float(trade.commission) if trade.commission is not None else None,
            trade.commission_asset,
            trade.is_maker,
            trade.source_type,
        ])

    for column_cells in ws.columns:
        max_length = 0
        column_letter = column_cells[0].column_letter
        for cell in column_cells:
            value = "" if cell.value is None else str(cell.value)
            if len(value) > max_length:
                max_length = len(value)
        ws.column_dimensions[column_letter].width = min(max_length + 2, 28)

    output = BytesIO()
    wb.save(output)
    output.seek(0)

    filename = "binance_futures_trades.xlsx"

    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )