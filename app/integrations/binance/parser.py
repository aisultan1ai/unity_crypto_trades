from __future__ import annotations

import csv
import io
import zipfile
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any


def _normalize_key(key: Any) -> str:
    if key is None:
        return ""
    text = str(key).strip().lower()
    for ch in [" ", "_", "-", "(", ")", ".", "/", "\\"]:
        text = text.replace(ch, "")
    return text


def _normalized_row(row: dict[str, Any]) -> dict[str, Any]:
    return {_normalize_key(k): v for k, v in row.items()}


def _pick_value(row: dict[str, Any], *aliases: str) -> Any:
    normalized = _normalized_row(row)
    for alias in aliases:
        key = _normalize_key(alias)
        if key in normalized:
            value = normalized[key]
            if value not in (None, "", "null"):
                return value
    return None


def to_decimal(value: Any) -> Decimal | None:
    if value in (None, "", "null"):
        return None

    text = str(value).strip()

    # Binance archive example:
    # "0.00264835 USDT"
    # берем только числовую часть до пробела
    if " " in text:
        text = text.split()[0]

    return Decimal(text)


def to_int(value: Any) -> int | None:
    if value in (None, "", "null"):
        return None
    return int(str(value))


def to_bool(value: Any) -> bool | None:
    if value in (None, "", "null"):
        return None
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"true", "1", "yes", "y"}


def to_trade_datetime(value: Any) -> datetime:
    if value in (None, "", "null"):
        raise ValueError("Trade time column is missing or empty")

    text = str(value).strip()

    # unix ms
    if text.isdigit():
        return datetime.fromtimestamp(int(text) / 1000, tz=timezone.utc)

    # archive format: 2026-04-13 16:42:35
    try:
        return datetime.strptime(text, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
    except ValueError:
        pass

    # fallback ISO
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"Unsupported trade time format: {text}") from exc


def parse_fee_asset(value: Any) -> str | None:
    if value in (None, "", "null"):
        return None

    text = str(value).strip()
    parts = text.split()

    # "0.00264835 USDT" -> USDT
    if len(parts) >= 2:
        return parts[1].strip()

    return None


def normalize_trade_row(row: dict[str, Any]) -> dict[str, Any]:
    buyer = to_bool(_pick_value(row, "buyer", "isBuyer"))
    side = _pick_value(row, "side", "orderSide")
    if not side and buyer is not None:
        side = "BUY" if buyer else "SELL"

    trade_time_raw = _pick_value(
        row,
        "time",
        "timestamp",
        "timeutc",
        "time(utc)",
        "tradetime",
    )

    if trade_time_raw is None:
        raise ValueError(f"Trade time column not found. Available columns: {list(row.keys())}")

    fee_raw = _pick_value(row, "commission", "fee")
    commission_asset = _pick_value(row, "commissionAsset", "feeAsset", "asset")
    if not commission_asset:
        commission_asset = parse_fee_asset(fee_raw)

    return {
        "symbol": _pick_value(row, "symbol", "pair", "contract"),
        "trade_id": to_int(_pick_value(row, "id", "tradeId", "trade id")),
        "order_id": to_int(_pick_value(row, "orderId", "order id")),
        "side": side,
        "position_side": _pick_value(row, "positionSide", "position side"),
        "price": to_decimal(_pick_value(row, "price", "avgPrice", "fillPrice")),
        "qty": to_decimal(_pick_value(row, "qty", "quantity", "executedQty", "size")),
        "quote_qty": to_decimal(_pick_value(row, "quoteQty", "quote quantity", "amount", "notional")),
        "realized_pnl": to_decimal(_pick_value(row, "realizedPnl", "realized pnl", "realized profit", "pnl")),
        "commission": to_decimal(fee_raw),
        "commission_asset": commission_asset,
        "is_maker": to_bool(_pick_value(row, "maker", "isMaker")),
        "trade_time": to_trade_datetime(trade_time_raw),
        "raw_payload": row,
    }


def parse_rest_trade_row(row: dict[str, Any]) -> dict[str, Any]:
    fee_raw = _pick_value(row, "commission")
    commission_asset = _pick_value(row, "commissionAsset")

    return {
        "symbol": _pick_value(row, "symbol"),
        "trade_id": to_int(_pick_value(row, "id")),
        "order_id": to_int(_pick_value(row, "orderId")),
        "side": _pick_value(row, "side"),
        "position_side": _pick_value(row, "positionSide"),
        "price": to_decimal(_pick_value(row, "price")),
        "qty": to_decimal(_pick_value(row, "qty")),
        "quote_qty": to_decimal(_pick_value(row, "quoteQty")),
        "realized_pnl": to_decimal(_pick_value(row, "realizedPnl")),
        "commission": to_decimal(fee_raw),
        "commission_asset": commission_asset,
        "is_maker": to_bool(_pick_value(row, "maker")),
        "trade_time": to_trade_datetime(_pick_value(row, "time")),
        "raw_payload": row,
    }


def _read_csv_bytes(content: bytes) -> list[dict[str, Any]]:
    text = content.decode("utf-8-sig", errors="replace")
    reader = csv.DictReader(io.StringIO(text))
    print("CSV HEADERS:", reader.fieldnames)

    rows = []
    for raw_row in reader:
        try:
            rows.append(normalize_trade_row(raw_row))
        except Exception as exc:
            print("SKIPPED ROW:", raw_row)
            print("ROW ERROR:", exc)
            continue

    return rows


def parse_archive_file(content: bytes) -> list[dict[str, Any]]:
    if content[:2] == b"PK":
        with zipfile.ZipFile(io.BytesIO(content)) as zf:
            for name in zf.namelist():
                if name.lower().endswith(".csv"):
                    with zf.open(name) as f:
                        return _read_csv_bytes(f.read())
        return []

    return _read_csv_bytes(content)