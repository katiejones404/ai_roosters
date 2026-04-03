import React, { useState, useEffect, useMemo } from "react";
import { useParams, useNavigate } from "react-router-dom";
import axios from "axios";
import AddToPortfolioModal from "./components/AddToPortfolio";

import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
} from "recharts";

import { StockSentimentCard } from "./SentimentIndicators";
import { fetchLatestStockIndicator } from "./utils/sentiment";
import type { StockIndicators } from "./utils/sentiment";
import LoadingScreen from "./components/LoadingScreen";

const API_BASE = (import.meta.env.VITE_API_BASE_URL || "http://localhost:8000").replace(/\/+$/, "");

const palette = {
  pageBg: "radial-gradient(circle at top, #101a31 0%, #070b14 45%, #050912 100%)",
  panel: "rgba(15, 23, 42, 0.92)",
  panelAlt: "rgba(17, 28, 49, 0.9)",
  border: "rgba(148, 163, 184, 0.24)",
  text: "#e2e8f0",
  muted: "#94a3b8",
  faintText: "#cbd5e1",
};

interface PriceData {
  ticker: string;
  date: string;
  close: number | null;
  adjusted_close: number | null;
  return_1d: number | null;
  return_30d: number | null;
  return_120d: number | null;
  return_360d: number | null;
}

const formatCurrency = (value: number | null | undefined): string => {
  if (value == null || Number.isNaN(value)) return "N/A";
  return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(value);
};

const formatPercent = (value: number | null | undefined): string => {
  if (value == null || Number.isNaN(value)) return "N/A";
  return `${value >= 0 ? "+" : ""}${(value * 100).toFixed(2)}%`;
};

const getReturnColor = (value: number | null | undefined): string => {
  if (value == null || Number.isNaN(value)) return "#6b7280";
  return value >= 0 ? "#22c55e" : "#ef4444";
};

const calcReturn = (from: number | null, to: number | null): number | null => {
  if (from == null || to == null) return null;
  if (Number.isNaN(from) || Number.isNaN(to)) return null;
  if (from === 0) return null;
  return (to - from) / from;
};

const CustomTooltip = ({ active, payload, label }: any) => {
  if (!active || !payload?.length) return null;
  return (
    <div
      style={{
        background: "#0f172a",
        border: `1px solid ${palette.border}`,
        borderRadius: 10,
        padding: "10px 14px",
        boxShadow: "0 10px 28px rgba(2, 6, 23, 0.55)",
      }}
    >
      <p style={{ margin: 0, fontSize: 12, color: palette.muted }}>
        {new Date(label).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" })}
      </p>
      <p style={{ margin: "4px 0 0", fontSize: 16, fontWeight: 700, color: palette.text }}>
        {formatCurrency(payload[0].value)}
      </p>
    </div>
  );
};

const toNumOrNull = (v: any): number | null => {
  if (v == null) return null;
  const n = typeof v === "number" ? v : Number(v);
  return Number.isFinite(n) ? n : null;
};

const normalizeAndSortPrices = (raw: any[], ticker?: string): PriceData[] => {
  const cleaned: PriceData[] = (raw || [])
    .map((d: any) => {
      const dateStr = typeof d?.date === "string" ? d.date : "";
      return {
        ticker: (d?.ticker ?? ticker ?? "").toString(),
        date: dateStr,
        close: toNumOrNull(d?.close),
        adjusted_close: toNumOrNull(d?.adjusted_close),
        return_1d: toNumOrNull(d?.return_1d),
        return_30d: toNumOrNull(d?.return_30d),
        return_120d: toNumOrNull(d?.return_120d),
        return_360d: toNumOrNull(d?.return_360d),
      };
    })
    .filter((d) => d.date && !Number.isNaN(new Date(d.date).getTime()));

  cleaned.sort((a, b) => new Date(a.date).getTime() - new Date(b.date).getTime());
  return cleaned;
};

const StockDetail: React.FC = () => {
  const { ticker } = useParams<{ ticker: string }>();
  const navigate = useNavigate();
  const normalizedTicker = (ticker ?? "").trim().toUpperCase();

  const [allData, setAllData] = useState<PriceData[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [timeRange, setTimeRange] = useState<"7" | "30" | "120" | "360">("30");
  const [showModal, setShowModal] = useState(false);

  const [sentiment, setSentiment] = useState<StockIndicators | null>(null);
  const [sentimentLoading, setSentimentLoading] = useState(false);
  const [sentimentError, setSentimentError] = useState<string | null>(null);

  useEffect(() => {
    if (!normalizedTicker) return;
    setLoading(true);

    axios
      .get<any[]>(`${API_BASE}/api/stocks/${encodeURIComponent(normalizedTicker)}/prices`)
      .then((res) => {
        const normalized = normalizeAndSortPrices(res.data, normalizedTicker);
        setAllData(normalized);
        setError(null);
      })
      .catch((err: unknown) => {
        if (axios.isAxiosError(err) && err.response?.status === 404) {
          setError(`No price history found for ${normalizedTicker}`);
          return;
        }
        setError("Failed to load stock data");
      })
      .finally(() => setLoading(false));
  }, [normalizedTicker]);

  useEffect(() => {
    if (!normalizedTicker) return;

    setSentimentLoading(true);
    setSentimentError(null);

    fetchLatestStockIndicator(normalizedTicker)
      .then((one) => setSentiment(one))
      .catch(() => {
        setSentiment(null);
        setSentimentError("Failed to load sentiment and AI news summary");
      })
      .finally(() => setSentimentLoading(false));
  }, [normalizedTicker]);

  const latest = allData.length ? allData[allData.length - 1] : null;
  const oldest = allData.length ? allData[0] : null;

  const chartData = useMemo(() => {
    if (!allData.length || !latest) return [];
    const days = parseInt(timeRange, 10);
    const lastDate = new Date(latest.date);
    const cutoff = new Date(lastDate);
    cutoff.setDate(cutoff.getDate() - days);

    return allData
      .filter((d) => d.close != null && new Date(d.date) >= cutoff)
      .map((d) => ({ date: d.date, close: d.close as number }));
  }, [allData, latest, timeRange]);

  const getPriceNDaysAgo = (days: number): number | null => {
    if (!latest) return null;
    const lastDate = new Date(latest.date);
    const targetDate = new Date(lastDate);
    targetDate.setDate(targetDate.getDate() - days);

    const candidates = allData.filter((d) => d.close != null && new Date(d.date) <= targetDate);
    if (!candidates.length) return null;
    return candidates[candidates.length - 1].close;
  };

  const ret1d = latest?.return_1d ?? calcReturn(getPriceNDaysAgo(1), latest?.close ?? null);
  const ret30d = latest?.return_30d ?? calcReturn(getPriceNDaysAgo(30), latest?.close ?? null);
  const ret120d = latest?.return_120d ?? calcReturn(getPriceNDaysAgo(120), latest?.close ?? null);
  const ret360d = latest?.return_360d ?? calcReturn(getPriceNDaysAgo(360), latest?.close ?? null);

  const rangeFirst = chartData[0]?.close ?? null;
  const rangeLast = chartData[chartData.length - 1]?.close ?? null;
  const rangeChange = calcReturn(rangeFirst, rangeLast);
  const isPositive = (rangeChange ?? 0) >= 0;
  const accentColor = isPositive ? "#22c55e" : "#ef4444";

  const chartStartDate = chartData.length ? chartData[0].date : null;
  const chartEndDate = chartData.length ? chartData[chartData.length - 1].date : null;

  if (loading) {
    return (
      <div style={{ minHeight: "100vh", background: palette.pageBg, display: "flex", alignItems: "center", justifyContent: "center" }}>
        <LoadingScreen message={`Loading ${normalizedTicker || ticker}...`} />
      </div>
    );
  }

  if (error) {
    return (
      <div style={{ minHeight: "100vh", background: palette.pageBg, display: "flex", alignItems: "center", justifyContent: "center" }}>
        <div style={{ textAlign: "center" }}>
          <p style={{ color: "#ef4444", fontSize: 18 }}>{error}</p>
          <button onClick={() => navigate("/dashboard")} style={{ marginTop: 16, padding: "10px 24px", background: "#4f46e5", color: "#fff", border: "none", borderRadius: 10, cursor: "pointer", fontWeight: 600 }}>
            {"<- Back to Dashboard"}
          </button>
        </div>
      </div>
    );
  }

  return (
    <div style={{ minHeight: "100vh", background: palette.pageBg, fontFamily: "system-ui, sans-serif", color: palette.text }}>
      <style>{`
        @keyframes fadeUp { from { opacity:0; transform:translateY(10px); } to { opacity:1; transform:translateY(0); } }
        .stat-card { animation: fadeUp 0.3s ease both; }
        .stat-card:nth-child(1) { animation-delay: 0.05s; }
        .stat-card:nth-child(2) { animation-delay: 0.10s; }
        .stat-card:nth-child(3) { animation-delay: 0.15s; }
        .stat-card:nth-child(4) { animation-delay: 0.20s; }
        .range-btn { border: none; border-radius: 8px; padding: 6px 14px; font-size: 13px; font-weight: 600; cursor: pointer; transition: all 0.15s ease; }
        .perf-row { display: flex; justify-content: space-between; align-items: center; padding: 12px 0; border-bottom: 1px solid ${palette.border}; }
        .perf-row:last-child { border-bottom: none; }
      `}</style>

      <div style={{ background: palette.panel, borderBottom: `1px solid ${palette.border}`, padding: "16px 32px", display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: 12 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
          <button onClick={() => navigate(-1)} style={{ background: "rgba(15, 23, 42, 0.8)", border: `1px solid ${palette.border}`, color: palette.faintText, borderRadius: 8, padding: "8px 14px", cursor: "pointer", fontSize: 14, fontWeight: 500 }}>
            {"<- Back"}
          </button>

          <div>
            <div style={{ display: "flex", alignItems: "baseline", gap: 12, flexWrap: "wrap" }}>
              <h1 style={{ margin: 0, fontSize: 28, fontWeight: 800, letterSpacing: "-0.02em" }}>{normalizedTicker || ticker}</h1>

              {latest?.close != null && (
                <span style={{ fontSize: 22, fontWeight: 600, color: palette.faintText }}>
                  {formatCurrency(latest.close)}
                </span>
              )}

              {rangeChange != null && (
                <span style={{ fontSize: 13, fontWeight: 600, color: accentColor, background: isPositive ? "rgba(22, 163, 74, 0.15)" : "rgba(220, 38, 38, 0.15)", padding: "3px 10px", borderRadius: 20 }}>
                  {formatPercent(rangeChange)} ({timeRange}D)
                </span>
              )}
            </div>

            {oldest && latest && (
              <p style={{ margin: "2px 0 0", fontSize: 12, color: palette.muted }}>
                Data from {new Date(oldest.date).toLocaleDateString()} - {new Date(latest.date).toLocaleDateString()}
                {chartStartDate && chartEndDate && (
                  <>
                    {" "}* Chart: {new Date(chartStartDate).toLocaleDateString()} - {new Date(chartEndDate).toLocaleDateString()}
                  </>
                )}
              </p>
            )}
          </div>
        </div>

        <button onClick={() => setShowModal(true)} style={{ background: "linear-gradient(135deg, #4f46e5, #0ea5e9)", color: "#fff", border: "none", borderRadius: 10, padding: "10px 22px", fontWeight: 600, fontSize: 14, cursor: "pointer" }}>
          + Add to Portfolio
        </button>
      </div>

      <div style={{ maxWidth: 1100, margin: "0 auto", padding: "32px 24px" }}>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(200px, 1fr))", gap: 16, marginBottom: 28 }}>
          {[
            { label: "Current Price", value: formatCurrency(latest?.close), color: palette.text },
            { label: "1-Day Return", value: formatPercent(ret1d), color: getReturnColor(ret1d) },
            { label: "30-Day Return", value: formatPercent(ret30d), color: getReturnColor(ret30d) },
            { label: "120-Day Return", value: formatPercent(ret120d), color: getReturnColor(ret120d) },
            { label: "360-Day Return", value: formatPercent(ret360d), color: getReturnColor(ret360d) },
          ].map(({ label, value, color }) => (
            <div key={label} className="stat-card" style={{ background: palette.panelAlt, border: `1px solid ${palette.border}`, borderRadius: 14, padding: "20px 22px" }}>
              <p style={{ margin: 0, fontSize: 11, color: palette.muted, textTransform: "uppercase", letterSpacing: "0.08em" }}>{label}</p>
              <p style={{ margin: "8px 0 0", fontSize: 22, fontWeight: 700, color }}>{value}</p>
            </div>
          ))}
        </div>

        <div style={{ marginBottom: 28, background: palette.panelAlt, border: `1px solid ${palette.border}`, borderRadius: 16, padding: 24 }}>
          <h2 style={{ margin: "0 0 12px", fontSize: 17, fontWeight: 700 }}>Sentiment and AI News Summary</h2>

          {sentimentLoading && <div style={{ color: palette.muted }}>Loading sentiment and AI news summary...</div>}
          {!sentimentLoading && sentimentError && <div style={{ color: "#ef4444" }}>{sentimentError}</div>}
          {!sentimentLoading && !sentimentError && sentiment && <StockSentimentCard data={sentiment} />}
          {!sentimentLoading && !sentimentError && !sentiment && <div style={{ color: palette.muted }}>No sentiment snapshot found for {normalizedTicker}.</div>}
        </div>

        <div style={{ background: palette.panelAlt, border: `1px solid ${palette.border}`, borderRadius: 16, padding: 24, marginBottom: 28 }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 20, flexWrap: "wrap", gap: 12 }}>
            <h2 style={{ margin: 0, fontSize: 17, fontWeight: 700 }}>Price History</h2>
            <div style={{ display: "flex", gap: 6 }}>
              {(["7", "30", "120", "360"] as const).map((d) => (
                <button
                  key={d}
                  className="range-btn"
                  onClick={() => setTimeRange(d)}
                  style={{ background: timeRange === d ? accentColor : "rgba(15, 23, 42, 0.78)", color: timeRange === d ? "#fff" : palette.faintText }}
                >
                  {d === "7" ? "1W" : d === "30" ? "1M" : d === "120" ? "4M" : "1Y"}
                </button>
              ))}
            </div>
          </div>

          {chartData.length === 0 ? (
            <div style={{ height: 280, display: "flex", alignItems: "center", justifyContent: "center", color: palette.muted }}>No data for this range</div>
          ) : (
            <ResponsiveContainer width="100%" height={300}>
              <LineChart data={chartData} margin={{ top: 5, right: 10, left: 5, bottom: 5 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(148, 163, 184, 0.16)" vertical={false} />
                <XAxis
                  dataKey="date"
                  tick={{ fill: palette.muted, fontSize: 11 }}
                  axisLine={false}
                  tickLine={false}
                  tickFormatter={(d: string) => new Date(d).toLocaleDateString("en-US", { month: "short", day: "numeric" })}
                />
                <YAxis
                  tick={{ fill: palette.muted, fontSize: 11 }}
                  axisLine={false}
                  tickLine={false}
                  tickFormatter={(v: number) => `$${v.toFixed(0)}`}
                  domain={["auto", "auto"]}
                  width={65}
                />
                <Tooltip content={<CustomTooltip />} />
                <Line type="monotone" dataKey="close" stroke={accentColor} strokeWidth={2.5} dot={false} activeDot={{ r: 5, fill: accentColor, strokeWidth: 0 }} />
              </LineChart>
            </ResponsiveContainer>
          )}
        </div>
      </div>

      {showModal && ticker && (
        <AddToPortfolioModal
          ticker={normalizedTicker}
          currentPrice={latest?.close ?? 0}
          onClose={() => setShowModal(false)}
          onSuccess={() => {
            setShowModal(false);
            navigate("/portfolio");
          }}
        />
      )}
    </div>
  );
};

export default StockDetail;
