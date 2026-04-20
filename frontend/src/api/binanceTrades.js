const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

async function http(url, options = {}) {
  const res = await fetch(`${API_BASE}${url}`, {
    headers: {
      "Content-Type": "application/json",
    },
    ...options,
  });

  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || `HTTP ${res.status}`);
  }

  return res.json();
}

export async function syncSubaccounts() {
  return http("/api/binance/subaccounts/sync", {
    method: "POST",
  });
}

export async function fetchSubaccounts() {
  return http("/api/binance/subaccounts");
}

export async function fetchSyncJobs() {
  return http("/api/binance/sync-jobs");
}

export async function fetchTrades(params = {}) {
  const qs = new URLSearchParams();

  if (params.subaccount_email) qs.set("subaccount_email", params.subaccount_email);
  if (params.symbol) qs.set("symbol", params.symbol);
  if (params.date_from) qs.set("date_from", params.date_from);
  if (params.date_to) qs.set("date_to", params.date_to);
  qs.set("limit", String(params.limit ?? 200));

  return http(`/api/binance/trades?${qs.toString()}`);
}

export async function runArchiveBackfill(payload) {
  return http("/api/binance/archive-backfill", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function runIncrementalSync(payload) {
  return http("/api/binance/incremental-sync", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function getTradesExportUrl(params = {}) {
  const qs = new URLSearchParams();

  if (params.subaccount_email) qs.set("subaccount_email", params.subaccount_email);
  if (params.symbol) qs.set("symbol", params.symbol);
  if (params.date_from) qs.set("date_from", params.date_from);
  if (params.date_to) qs.set("date_to", params.date_to);

  return `${API_BASE}/api/binance/trades/export?${qs.toString()}`;
}