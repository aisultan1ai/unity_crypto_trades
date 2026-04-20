from __future__ import annotations

import time
from datetime import datetime, timezone

import requests
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.integrations.binance.client import BinanceSignedClient
from app.integrations.binance.parser import parse_archive_file, parse_rest_trade_row
from app.models.binance import (
    BinanceSubAccount,
    BinanceSyncJob,
    FuturesSymbolRegistry,
    FuturesTrade,
)


class BinanceClientFactory:
    def __init__(
        self,
        master_client: BinanceSignedClient,
        subaccount_keys: dict[str, dict[str, str]],
        spot_base_url: str,
        futures_base_url: str,
        recv_window: int,
    ) -> None:
        self.master_client = master_client
        self.subaccount_keys = subaccount_keys
        self.spot_base_url = spot_base_url
        self.futures_base_url = futures_base_url
        self.recv_window = recv_window

    def get_subaccount_futures_client(self, email: str) -> BinanceSignedClient:
        creds = self.subaccount_keys.get(email)
        if not creds:
            raise ValueError(f"No API credentials configured for subaccount: {email}")

        return BinanceSignedClient(
            api_key=creds["api_key"],
            api_secret=creds["api_secret"],
            spot_base_url=self.spot_base_url,
            futures_base_url=self.futures_base_url,
            recv_window=self.recv_window,
        )


def sync_subaccounts(db: Session, master_client: BinanceSignedClient) -> int:
    updated = 0
    page = 1

    while True:
        data = master_client.get_subaccounts(page=page, limit=200)
        items = data.get("subAccounts", [])

        if not items:
            break

        for item in items:
            existing = db.scalar(
                select(BinanceSubAccount).where(BinanceSubAccount.email == item["email"])
            )
            if not existing:
                existing = BinanceSubAccount(email=item["email"])
                db.add(existing)

            existing.remark = item.get("remark")
            existing.is_frozen = bool(item.get("isFreeze", False))
            existing.is_managed = bool(item.get("isManagedSubAccount", False))
            updated += 1

        if len(items) < 200:
            break

        page += 1

    db.commit()
    return updated


def create_sync_job(
    db: Session,
    subaccount_id: int,
    job_type: str,
    period_start: datetime,
    period_end: datetime,
) -> BinanceSyncJob:
    job = BinanceSyncJob(
        subaccount_id=subaccount_id,
        job_type=job_type,
        status="queued",
        period_start=period_start,
        period_end=period_end,
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def _download_archive_until_ready(
    futures_client: BinanceSignedClient,
    start_ms: int,
    end_ms: int,
    poll_seconds: int = 5,
    max_wait_seconds: int = 180,
) -> tuple[str, str]:
    resp = futures_client.request_trade_archive(start_ms, end_ms)
    download_id = resp["downloadId"]

    started = time.time()
    while True:
        status_data = futures_client.get_trade_archive_link(download_id)
        status = status_data.get("status")

        if status == "completed" and status_data.get("url"):
            return download_id, status_data["url"]

        if time.time() - started > max_wait_seconds:
            raise TimeoutError("Archive generation timed out")

        time.sleep(poll_seconds)


def _upsert_trade(
    db: Session,
    subaccount: BinanceSubAccount,
    trade: dict,
    source_type: str,
) -> bool:
    exists = db.scalar(
        select(FuturesTrade).where(
            FuturesTrade.subaccount_id == subaccount.id,
            FuturesTrade.symbol == trade["symbol"],
            FuturesTrade.trade_id == trade["trade_id"],
        )
    )
    if exists:
        return False

    row = FuturesTrade(
        subaccount_id=subaccount.id,
        symbol=trade["symbol"],
        trade_id=trade["trade_id"],
        order_id=trade.get("order_id"),
        side=trade.get("side"),
        position_side=trade.get("position_side"),
        price=trade.get("price"),
        qty=trade.get("qty"),
        quote_qty=trade.get("quote_qty"),
        realized_pnl=trade.get("realized_pnl"),
        commission=trade.get("commission"),
        commission_asset=trade.get("commission_asset"),
        is_maker=trade.get("is_maker"),
        trade_time=trade["trade_time"],
        source_type=source_type,
        raw_payload=trade.get("raw_payload"),
    )
    db.add(row)
    return True


def rebuild_symbol_registry(db: Session, subaccount_id: int) -> None:
    aggregated = db.execute(
        select(
            FuturesTrade.symbol,
            func.min(FuturesTrade.trade_time).label("first_seen_at"),
            func.max(FuturesTrade.trade_time).label("last_seen_at"),
        )
        .where(FuturesTrade.subaccount_id == subaccount_id)
        .group_by(FuturesTrade.symbol)
    ).all()

    existing_rows = db.scalars(
        select(FuturesSymbolRegistry).where(
            FuturesSymbolRegistry.subaccount_id == subaccount_id
        )
    ).all()

    existing_map = {row.symbol: row for row in existing_rows}

    for symbol, first_seen_at, last_seen_at in aggregated:
        row = existing_map.get(symbol)
        if row is None:
            db.add(
                FuturesSymbolRegistry(
                    subaccount_id=subaccount_id,
                    symbol=symbol,
                    first_seen_at=first_seen_at,
                    last_seen_at=last_seen_at,
                )
            )
        else:
            row.first_seen_at = first_seen_at
            row.last_seen_at = last_seen_at


def run_archive_backfill(
    db: Session,
    client_factory: BinanceClientFactory,
    job_id: int,
) -> dict:
    job = db.get(BinanceSyncJob, job_id)
    if not job:
        raise ValueError("Sync job not found")

    subaccount = db.get(BinanceSubAccount, job.subaccount_id)
    if not subaccount:
        raise ValueError("Subaccount not found")

    futures_client = client_factory.get_subaccount_futures_client(subaccount.email)

    job.status = "processing"
    job.started_at = datetime.now(timezone.utc)
    db.commit()

    try:
        start_ms = int(job.period_start.timestamp() * 1000)
        end_ms = int(job.period_end.timestamp() * 1000)

        download_id, download_url = _download_archive_until_ready(
            futures_client=futures_client,
            start_ms=start_ms,
            end_ms=end_ms,
        )

        job.download_id = download_id
        job.download_url = download_url
        db.commit()

        file_resp = requests.get(download_url, timeout=120)
        file_resp.raise_for_status()

        normalized_rows = parse_archive_file(file_resp.content)
        print("ARCHIVE ROWS COUNT:", len(normalized_rows))

        inserted = 0
        for trade in normalized_rows:
            if not trade.get("symbol") or not trade.get("trade_id"):
                continue
            inserted += int(_upsert_trade(db, subaccount, trade, source_type="archive"))

        db.commit()

        rebuild_symbol_registry(db, subaccount.id)

        subaccount.last_archive_sync_at = datetime.now(timezone.utc)
        job.rows_loaded = inserted
        job.status = "completed"
        job.finished_at = datetime.now(timezone.utc)
        db.commit()

        return {
            "job_id": job.id,
            "status": job.status,
            "rows_loaded": inserted,
            "download_id": download_id,
        }

    except Exception as exc:
        db.rollback()
        job = db.get(BinanceSyncJob, job_id)
        if job:
            job.status = "failed"
            job.error_text = str(exc)
            job.finished_at = datetime.now(timezone.utc)
            db.commit()
        raise


def incremental_sync_symbol(
    db: Session,
    client_factory: BinanceClientFactory,
    subaccount_id: int,
    symbol: str,
    start_ms: int,
    end_ms: int,
) -> dict:
    subaccount = db.get(BinanceSubAccount, subaccount_id)
    if not subaccount:
        raise ValueError("Subaccount not found")

    futures_client = client_factory.get_subaccount_futures_client(subaccount.email)

    rows = futures_client.get_user_trades(
        symbol=symbol,
        start_time_ms=start_ms,
        end_time_ms=end_ms,
        limit=1000,
    )

    inserted = 0
    for row in rows:
        trade = parse_rest_trade_row(row)
        if not trade.get("symbol") or not trade.get("trade_id"):
            continue
        inserted += int(_upsert_trade(db, subaccount, trade, source_type="rest"))

    db.commit()

    rebuild_symbol_registry(db, subaccount.id)

    subaccount.last_incremental_sync_at = datetime.now(timezone.utc)
    db.commit()

    return {
        "subaccount_id": subaccount.id,
        "symbol": symbol,
        "fetched": len(rows),
        "inserted": inserted,
    }