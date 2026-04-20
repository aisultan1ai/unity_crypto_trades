import React, { useEffect, useMemo, useState } from "react";
import {
  fetchSubaccounts,
  fetchSyncJobs,
  fetchTrades,
  runArchiveBackfill,
  runIncrementalSync,
  syncSubaccounts,
  getTradesExportUrl,
} from "../api/binanceTrades";

function fmtDate(value) {
  if (!value) return "—";
  return new Date(value).toLocaleString();
}

function toIsoLocal(date, endOfDay = false) {
  if (!date) return "";
  const suffix = endOfDay ? "T23:59:59" : "T00:00:00";
  return new Date(`${date}${suffix}`).toISOString();
}

const boxStyle = {
  border: "1px solid #ddd",
  borderRadius: "12px",
  padding: "16px",
  background: "#fff",
};

const inputStyle = {
  padding: "10px",
  border: "1px solid #ccc",
  borderRadius: "8px",
  width: "100%",
};

const buttonStyle = {
  padding: "10px 14px",
  border: "none",
  borderRadius: "8px",
  background: "#111",
  color: "#fff",
  cursor: "pointer",
};

const secondaryButtonStyle = {
  padding: "10px 14px",
  border: "1px solid #ccc",
  borderRadius: "8px",
  background: "#fff",
  cursor: "pointer",
};

const statusStyle = {
  queued: { color: "#8a6d3b" },
  processing: { color: "#1565c0" },
  completed: { color: "#2e7d32" },
  failed: { color: "#c62828" },
};

export default function BinanceFuturesTradesPage() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const [subaccounts, setSubaccounts] = useState([]);
  const [jobs, setJobs] = useState([]);
  const [trades, setTrades] = useState([]);

  const [selectedSub, setSelectedSub] = useState("");
  const [symbol, setSymbol] = useState("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [limit, setLimit] = useState(200);

  const [archiveSub, setArchiveSub] = useState("");
  const [archiveStart, setArchiveStart] = useState("");
  const [archiveEnd, setArchiveEnd] = useState("");

  const [incSub, setIncSub] = useState("");
  const [incSymbol, setIncSymbol] = useState("");
  const [incStart, setIncStart] = useState("");
  const [incEnd, setIncEnd] = useState("");

  async function loadAll() {
    setLoading(true);
    setError("");

    try {
      const [subs, syncJobs, tradeRows] = await Promise.all([
        fetchSubaccounts(),
        fetchSyncJobs(),
        fetchTrades({
          subaccount_email: selectedSub || undefined,
          symbol: symbol || undefined,
          date_from: dateFrom ? toIsoLocal(dateFrom) : undefined,
          date_to: dateTo ? toIsoLocal(dateTo, true) : undefined,
          limit,
        }),
      ]);

      setSubaccounts(subs);
      setJobs(syncJobs);
      setTrades(tradeRows);

      if (!archiveSub && subs.length > 0) setArchiveSub(subs[0].email);
      if (!incSub && subs.length > 0) setIncSub(subs[0].email);
    } catch (e) {
      setError(e.message || "Ошибка загрузки");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadAll();
  }, []);

  async function handleSyncSubaccounts() {
    setLoading(true);
    setError("");
    try {
      await syncSubaccounts();
      await loadAll();
    } catch (e) {
      setError(e.message || "Не удалось синхронизировать субсчета");
    } finally {
      setLoading(false);
    }
  }

  async function handleArchiveBackfill() {
    if (!archiveSub || !archiveStart || !archiveEnd) {
      setError("Выбери субсчет и период архива");
      return;
    }

    setLoading(true);
    setError("");

    try {
      await runArchiveBackfill({
        subaccount_email: archiveSub,
        period_start: toIsoLocal(archiveStart),
        period_end: toIsoLocal(archiveEnd, true),
      });
      await loadAll();
    } catch (e) {
      setError(e.message || "Ошибка archive backfill");
    } finally {
      setLoading(false);
    }
  }

  async function handleIncrementalSync() {
    if (!incSub || !incSymbol || !incStart || !incEnd) {
      setError("Заполни субсчет, symbol и период incremental sync");
      return;
    }

    setLoading(true);
    setError("");

    try {
      await runIncrementalSync({
        subaccount_email: incSub,
        symbol: incSymbol.toUpperCase(),
        period_start: toIsoLocal(incStart),
        period_end: toIsoLocal(incEnd, true),
      });
      await loadAll();
    } catch (e) {
      setError(e.message || "Ошибка incremental sync");
    } finally {
      setLoading(false);
    }
  }

  function handleExportExcel() {
    const url = getTradesExportUrl({
      subaccount_email: selectedSub || undefined,
      symbol: symbol || undefined,
      date_from: dateFrom ? toIsoLocal(dateFrom) : undefined,
      date_to: dateTo ? toIsoLocal(dateTo, true) : undefined,
    });

    window.open(url, "_blank");
  }

  const stats = useMemo(() => {
    let pnl = 0;
    let commission = 0;
    let volume = 0;

    for (const t of trades) {
      pnl += Number(t.realized_pnl || 0);
      commission += Number(t.commission || 0);
      volume += Number(t.quote_qty || 0);
    }

    return {
      count: trades.length,
      pnl,
      commission,
      volume,
    };
  }, [trades]);

  return (
    <div
      style={{
        maxWidth: "1400px",
        margin: "0 auto",
        padding: "20px",
        fontFamily: "Arial, sans-serif",
        background: "#f7f7f7",
      }}
    >
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          marginBottom: "20px",
        }}
      >
        <div>
          <h1 style={{ margin: 0 }}>Binance Futures Trades</h1>
          <p style={{ marginTop: "6px", color: "#666" }}>
            История сделок по субсчетам, archive backfill, incremental sync и экспорт
          </p>
        </div>

        <div style={{ display: "flex", gap: "10px" }}>
          <button onClick={handleSyncSubaccounts} style={buttonStyle} disabled={loading}>
            Синхронизировать субсчета
          </button>
          <button onClick={loadAll} style={secondaryButtonStyle} disabled={loading}>
            Обновить
          </button>
          <button onClick={handleExportExcel} style={secondaryButtonStyle} disabled={loading}>
            Экспорт в Excel
          </button>
        </div>
      </div>

      {error ? (
        <div
          style={{
            ...boxStyle,
            borderColor: "#e57373",
            background: "#fff0f0",
            color: "#b71c1c",
            marginBottom: "20px",
          }}
        >
          {error}
        </div>
      ) : null}

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(4, 1fr)",
          gap: "16px",
          marginBottom: "20px",
        }}
      >
        <div style={boxStyle}>
          <div style={{ color: "#666" }}>Субсчетов</div>
          <div style={{ fontSize: "28px", marginTop: "10px" }}>{subaccounts.length}</div>
        </div>
        <div style={boxStyle}>
          <div style={{ color: "#666" }}>Сделок в выборке</div>
          <div style={{ fontSize: "28px", marginTop: "10px" }}>{stats.count}</div>
        </div>
        <div style={boxStyle}>
          <div style={{ color: "#666" }}>Realized PnL</div>
          <div style={{ fontSize: "28px", marginTop: "10px" }}>{stats.pnl.toFixed(4)}</div>
        </div>
        <div style={boxStyle}>
          <div style={{ color: "#666" }}>Commission</div>
          <div style={{ fontSize: "28px", marginTop: "10px" }}>{stats.commission.toFixed(4)}</div>
        </div>
      </div>

      <div style={{ ...boxStyle, marginBottom: "20px" }}>
        <h2>Фильтры сделок</h2>
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "2fr 1fr 1fr 1fr 1fr",
            gap: "12px",
            marginBottom: "12px",
          }}
        >
          <select value={selectedSub} onChange={(e) => setSelectedSub(e.target.value)} style={inputStyle}>
            <option value="">Все субсчета</option>
            {subaccounts.map((sub) => (
              <option key={sub.id} value={sub.email}>
                {sub.email}
              </option>
            ))}
          </select>

          <input
            value={symbol}
            onChange={(e) => setSymbol(e.target.value.toUpperCase())}
            placeholder="BTCUSDT"
            style={inputStyle}
          />

          <input type="date" value={dateFrom} onChange={(e) => setDateFrom(e.target.value)} style={inputStyle} />
          <input type="date" value={dateTo} onChange={(e) => setDateTo(e.target.value)} style={inputStyle} />
          <input type="number" value={limit} onChange={(e) => setLimit(Number(e.target.value))} style={inputStyle} />
        </div>

        <button onClick={loadAll} style={buttonStyle} disabled={loading}>
          Применить фильтры
        </button>
      </div>

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "1fr 1fr",
          gap: "16px",
          marginBottom: "20px",
        }}
      >
        <div style={boxStyle}>
          <h2>Archive backfill</h2>
          <div style={{ display: "grid", gap: "12px" }}>
            <select value={archiveSub} onChange={(e) => setArchiveSub(e.target.value)} style={inputStyle}>
              <option value="">Выбери субсчет</option>
              {subaccounts.map((sub) => (
                <option key={sub.id} value={sub.email}>
                  {sub.email}
                </option>
              ))}
            </select>

            <input type="date" value={archiveStart} onChange={(e) => setArchiveStart(e.target.value)} style={inputStyle} />
            <input type="date" value={archiveEnd} onChange={(e) => setArchiveEnd(e.target.value)} style={inputStyle} />

            <button onClick={handleArchiveBackfill} style={buttonStyle} disabled={loading}>
              Запустить archive sync
            </button>
          </div>
        </div>

        <div style={boxStyle}>
          <h2>Incremental sync</h2>
          <div style={{ display: "grid", gap: "12px" }}>
            <select value={incSub} onChange={(e) => setIncSub(e.target.value)} style={inputStyle}>
              <option value="">Выбери субсчет</option>
              {subaccounts.map((sub) => (
                <option key={sub.id} value={sub.email}>
                  {sub.email}
                </option>
              ))}
            </select>

            <input
              value={incSymbol}
              onChange={(e) => setIncSymbol(e.target.value.toUpperCase())}
              placeholder="BTCUSDT"
              style={inputStyle}
            />

            <input type="date" value={incStart} onChange={(e) => setIncStart(e.target.value)} style={inputStyle} />
            <input type="date" value={incEnd} onChange={(e) => setIncEnd(e.target.value)} style={inputStyle} />

            <button onClick={handleIncrementalSync} style={buttonStyle} disabled={loading}>
              Запустить incremental sync
            </button>
          </div>
        </div>
      </div>

      <div style={{ ...boxStyle, marginBottom: "20px" }}>
        <h2>Sync jobs</h2>
        <div style={{ overflowX: "auto" }}>
          <table style={{ width: "100%", borderCollapse: "collapse" }}>
            <thead>
              <tr>
                <th style={{ textAlign: "left", padding: "10px", borderBottom: "1px solid #ddd" }}>ID</th>
                <th style={{ textAlign: "left", padding: "10px", borderBottom: "1px solid #ddd" }}>Type</th>
                <th style={{ textAlign: "left", padding: "10px", borderBottom: "1px solid #ddd" }}>Status</th>
                <th style={{ textAlign: "left", padding: "10px", borderBottom: "1px solid #ddd" }}>Period</th>
                <th style={{ textAlign: "left", padding: "10px", borderBottom: "1px solid #ddd" }}>Rows</th>
                <th style={{ textAlign: "left", padding: "10px", borderBottom: "1px solid #ddd" }}>Error</th>
              </tr>
            </thead>
            <tbody>
              {jobs.map((job) => (
                <tr key={job.id}>
                  <td style={{ padding: "10px", borderBottom: "1px solid #eee" }}>{job.id}</td>
                  <td style={{ padding: "10px", borderBottom: "1px solid #eee" }}>{job.job_type}</td>
                  <td
                    style={{
                      padding: "10px",
                      borderBottom: "1px solid #eee",
                      fontWeight: 700,
                      ...(statusStyle[job.status] || {}),
                    }}
                  >
                    {job.status}
                  </td>
                  <td style={{ padding: "10px", borderBottom: "1px solid #eee" }}>
                    {fmtDate(job.period_start)}
                    <br />
                    {fmtDate(job.period_end)}
                  </td>
                  <td style={{ padding: "10px", borderBottom: "1px solid #eee" }}>{job.rows_loaded}</td>
                  <td style={{ padding: "10px", borderBottom: "1px solid #eee", color: "#c62828" }}>
                    {job.error_text || "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <div style={boxStyle}>
        <h2>Trades</h2>
        <div style={{ overflowX: "auto" }}>
          <table style={{ width: "100%", borderCollapse: "collapse", minWidth: "1200px" }}>
            <thead>
              <tr>
                <th style={{ textAlign: "left", padding: "10px", borderBottom: "1px solid #ddd" }}>Time</th>
                <th style={{ textAlign: "left", padding: "10px", borderBottom: "1px solid #ddd" }}>Subaccount</th>
                <th style={{ textAlign: "left", padding: "10px", borderBottom: "1px solid #ddd" }}>Symbol</th>
                <th style={{ textAlign: "left", padding: "10px", borderBottom: "1px solid #ddd" }}>Side</th>
                <th style={{ textAlign: "left", padding: "10px", borderBottom: "1px solid #ddd" }}>Position</th>
                <th style={{ textAlign: "left", padding: "10px", borderBottom: "1px solid #ddd" }}>Qty</th>
                <th style={{ textAlign: "left", padding: "10px", borderBottom: "1px solid #ddd" }}>Price</th>
                <th style={{ textAlign: "left", padding: "10px", borderBottom: "1px solid #ddd" }}>Quote Qty</th>
                <th style={{ textAlign: "left", padding: "10px", borderBottom: "1px solid #ddd" }}>PnL</th>
                <th style={{ textAlign: "left", padding: "10px", borderBottom: "1px solid #ddd" }}>Commission</th>
                <th style={{ textAlign: "left", padding: "10px", borderBottom: "1px solid #ddd" }}>Maker</th>
                <th style={{ textAlign: "left", padding: "10px", borderBottom: "1px solid #ddd" }}>Source</th>
              </tr>
            </thead>
            <tbody>
              {trades.map((trade) => (
                <tr key={`${trade.subaccount_email}-${trade.symbol}-${trade.trade_id}`}>
                  <td style={{ padding: "10px", borderBottom: "1px solid #eee" }}>{fmtDate(trade.trade_time)}</td>
                  <td style={{ padding: "10px", borderBottom: "1px solid #eee" }}>{trade.subaccount_email}</td>
                  <td style={{ padding: "10px", borderBottom: "1px solid #eee" }}>{trade.symbol}</td>
                  <td style={{ padding: "10px", borderBottom: "1px solid #eee" }}>{trade.side || "—"}</td>
                  <td style={{ padding: "10px", borderBottom: "1px solid #eee" }}>{trade.position_side || "—"}</td>
                  <td style={{ padding: "10px", borderBottom: "1px solid #eee" }}>{trade.qty || "—"}</td>
                  <td style={{ padding: "10px", borderBottom: "1px solid #eee" }}>{trade.price || "—"}</td>
                  <td style={{ padding: "10px", borderBottom: "1px solid #eee" }}>{trade.quote_qty || "—"}</td>
                  <td style={{ padding: "10px", borderBottom: "1px solid #eee" }}>{trade.realized_pnl || "—"}</td>
                  <td style={{ padding: "10px", borderBottom: "1px solid #eee" }}>
                    {trade.commission || "—"} {trade.commission_asset || ""}
                  </td>
                  <td style={{ padding: "10px", borderBottom: "1px solid #eee" }}>{String(trade.is_maker ?? "—")}</td>
                  <td style={{ padding: "10px", borderBottom: "1px solid #eee" }}>{trade.source_type}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}