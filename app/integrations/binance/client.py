from __future__ import annotations

import hashlib
import hmac
import time
from typing import Any
from urllib.parse import urlencode

import requests


class BinanceAPIError(RuntimeError):
    pass


class BinanceSignedClient:
    def __init__(
        self,
        api_key: str,
        api_secret: str,
        spot_base_url: str,
        futures_base_url: str,
        recv_window: int = 5000,
        timeout: int = 30,
    ) -> None:
        self.api_key = api_key
        self.api_secret = api_secret.encode("utf-8")
        self.spot_base_url = spot_base_url.rstrip("/")
        self.futures_base_url = futures_base_url.rstrip("/")
        self.recv_window = recv_window
        self.timeout = timeout

        self.session = requests.Session()
        self.session.headers.update({"X-MBX-APIKEY": self.api_key})

    @staticmethod
    def _timestamp_ms() -> int:
        return int(time.time() * 1000)

    def _sign_params(self, params: dict[str, Any]) -> dict[str, Any]:
        signed = {k: v for k, v in params.items() if v is not None}
        signed["timestamp"] = self._timestamp_ms()
        signed["recvWindow"] = self.recv_window

        query = urlencode(signed, doseq=True)
        signature = hmac.new(
            self.api_secret,
            query.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

        signed["signature"] = signature
        return signed

    def _signed_get(self, base_url: str, path: str, params: dict[str, Any] | None = None) -> Any:
        signed = self._sign_params(params or {})
        url = f"{base_url}{path}"

        resp = self.session.get(url, params=signed, timeout=self.timeout)
        if not resp.ok:
            raise BinanceAPIError(f"{resp.status_code} {resp.text}")
        return resp.json()

    # Master account endpoints
    def get_subaccounts(self, page: int = 1, limit: int = 200) -> dict[str, Any]:
        return self._signed_get(
            self.spot_base_url,
            "/sapi/v1/sub-account/list",
            {"page": page, "limit": limit},
        )

    # Subaccount futures endpoints
    def request_trade_archive(self, start_time_ms: int, end_time_ms: int) -> dict[str, Any]:
        return self._signed_get(
            self.futures_base_url,
            "/fapi/v1/trade/asyn",
            {"startTime": start_time_ms, "endTime": end_time_ms},
        )

    def get_trade_archive_link(self, download_id: str) -> dict[str, Any]:
        return self._signed_get(
            self.futures_base_url,
            "/fapi/v1/trade/asyn/id",
            {"downloadId": download_id},
        )

    def get_user_trades(
        self,
        symbol: str,
        start_time_ms: int | None = None,
        end_time_ms: int | None = None,
        from_id: int | None = None,
        limit: int = 1000,
    ) -> list[dict[str, Any]]:
        return self._signed_get(
            self.futures_base_url,
            "/fapi/v1/userTrades",
            {
                "symbol": symbol,
                "startTime": start_time_ms,
                "endTime": end_time_ms,
                "fromId": from_id,
                "limit": limit,
            },
        )