/*
 * Alerts.tsx
 * Price alerts page where users create, view, and delete stock price alerts.
 */
import { useState, useEffect, useMemo, type FormEvent } from "react";
import axios from "axios";
import { useLocation } from "react-router-dom";
import "./Alerts.css";
import LoadingScreen from "./components/LoadingScreen";
import { getNotificationPreferences } from "./utils/auth";

const API_BASE = (
  import.meta.env.VITE_API_BASE_URL || "http://localhost:8000"
).replace(/\/+$/, "");

const WEBSITE_TICKERS = [
  "KSS", "ALK", "NVS", "AXP", "FCX",
  "CSX", "DAL", "NTAP", "MRK", "COP",
  "BHP", "EA",
  "TSLA", "NVDA", "AAPL", "MSFT", "AMZN",
  "AMD", "META", "GOOGL", "GOOG", "PLTR",
  "MU", "NFLX",
  "NKE", "AAL", "BAC", "F", "INTC", "XOM", "T",
  "SOFI", "PLUG", "MARA", "SNAP", "COIN", "AMC", "RIVN", "CCL", "ENPH",
];

interface Alert {
  id: string;
  ticker: string;
  target_price: number;
  direction: string;
  is_active: boolean;
  email_notify: boolean;
  triggered_at: string | null;
  triggered_price: number | null;
  created_at: string | null;
}

function formatDate(iso: string | null): string {
  if (!iso) return "-";
  return new Date(iso).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

export default function Alerts() {
  const location = useLocation();
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [marketAlertsEnabled, setMarketAlertsEnabled] = useState(false);
  const [prefsLoaded, setPrefsLoaded] = useState(false);
  const [ticker, setTicker] = useState(WEBSITE_TICKERS[0]);
  const [targetPrice, setTargetPrice] = useState("");
  const [direction, setDirection] = useState<"above" | "below">("above");
  const [creating, setCreating] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  const preselectedTicker = useMemo(() => {
    const raw = new URLSearchParams(location.search).get("ticker");
    return raw?.trim().toUpperCase() || "";
  }, [location.search]);

  const tickerOptions = useMemo(() => {
    if (!preselectedTicker) {
      return WEBSITE_TICKERS;
    }
    return WEBSITE_TICKERS.includes(preselectedTicker)
      ? WEBSITE_TICKERS
      : [preselectedTicker, ...WEBSITE_TICKERS];
  }, [preselectedTicker]);

  const fetchAlerts = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await axios.get<Alert[]>(`${API_BASE}/api/alerts`);
      setAlerts(res.data);
    } catch {
      setError("Failed to load alerts.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAlerts();
    getNotificationPreferences()
      .then((prefs) => {
        setMarketAlertsEnabled(prefs.marketAlerts);
      })
      .catch(() => {
        setMarketAlertsEnabled(false);
      })
      .finally(() => {
        setPrefsLoaded(true);
      });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (preselectedTicker) {
      setTicker(preselectedTicker);
    }
  }, [preselectedTicker]);

  const handleCreate = async (e: FormEvent) => {
    e.preventDefault();
    setFormError(null);
    const price = parseFloat(targetPrice);
    if (!targetPrice || Number.isNaN(price) || price <= 0) {
      setFormError("Enter a valid positive target price.");
      return;
    }

    // Prevent duplicate active alerts with the same ticker, direction, and target price
    const isDuplicate = alerts.some(
      (a) =>
        a.is_active &&
        a.ticker === ticker &&
        a.direction === direction &&
        a.target_price === price
    );
    if (isDuplicate) {
      setFormError(
        `An active alert already exists for ${ticker} ${direction === "above" ? "rising above" : "falling below"} $${price.toFixed(2)}.`
      );
      return;
    }

    setCreating(true);
    try {
      await axios.post(`${API_BASE}/api/alerts`, {
        ticker,
        target_price: price,
        direction,
        email_notify: marketAlertsEnabled,
      });
      setTargetPrice("");
      await fetchAlerts();
    } catch {
      setFormError("Failed to create alert. Please try again.");
    } finally {
      setCreating(false);
    }
  };

  const handleDelete = async (id: string) => {
    try {
      await axios.delete(`${API_BASE}/api/alerts/${id}`);
      setAlerts((prev) => prev.filter((a) => a.id !== id));
    } catch {
      setError("Failed to delete alert.");
    }
  };

  const active = alerts.filter((a) => a.is_active);
  const triggered = alerts.filter((a) => !a.is_active);

  const subtitle = !prefsLoaded
    ? "Get notified when a stock hits your target price"
    : marketAlertsEnabled
    ? "Get notified when a stock hits your target price"
    : "Get notified when a stock hits your target price. Turn on Market Alerts in settings to receive email alerts.";

  return (
    <div className="app-container app-container-wide">
      <div className="home-card alerts-card">
        <div className="alerts-header">
          <h1 className="alerts-title">Price Alerts</h1>
          <p className="alerts-subtitle">{subtitle}</p>
        </div>

        <div className="alert-form-card">
          <h2 className="alert-form-title">New Alert</h2>
          <form className="alert-form" onSubmit={handleCreate}>
            <div className="alert-form-row">
              <div className="alert-field">
                <label className="alert-label">Ticker</label>
                <select
                  className="alert-select"
                  value={ticker}
                  onChange={(e) => setTicker(e.target.value)}
                >
                  {tickerOptions.map((t) => (
                    <option key={t} value={t}>
                      {t}
                    </option>
                  ))}
                </select>
              </div>
              <div className="alert-field">
                <label className="alert-label">Condition</label>
                <select
                  className="alert-select"
                  value={direction}
                  onChange={(e) =>
                    setDirection(e.target.value as "above" | "below")
                  }
                >
                  <option value="above">Rises above</option>
                  <option value="below">Falls below</option>
                </select>
              </div>
              <div className="alert-field">
                <label className="alert-label">Target Price ($)</label>
                <input
                  className="alert-input"
                  type="number"
                  min="0.01"
                  step="0.01"
                  placeholder="e.g. 150.00"
                  value={targetPrice}
                  onChange={(e) => setTargetPrice(e.target.value)}
                />
              </div>
              <button
                className="alert-create-btn"
                type="submit"
                disabled={creating}
              >
                {creating ? "Creating..." : "+ Add Alert"}
              </button>
            </div>
            {formError && <p className="alert-form-error">{formError}</p>}
          </form>
        </div>

        {error && <p className="alerts-error">{error}</p>}

        {/* Active + Triggered side by side */}
        <div className="alerts-tables-row">
          <div className="alerts-section">
            <h2 className="alerts-section-title">Active Alerts</h2>
            {loading ? (
              <LoadingScreen message="Loading alerts..." />
            ) : active.length === 0 ? (
              <p className="alerts-empty">No active alerts. Create one above.</p>
            ) : (
              <div className="alerts-table-wrapper">
                <table className="alerts-table">
                  <thead>
                    <tr>
                      <th>Ticker</th>
                      <th>Condition</th>
                      <th>Target Price</th>
                      <th>Created</th>
                      <th></th>
                    </tr>
                  </thead>
                  <tbody>
                    {active.map((a) => (
                      <tr key={a.id}>
                        <td>
                          <span className="alert-ticker-badge">{a.ticker}</span>
                        </td>
                        <td className="alert-direction">
                          {a.direction === "above" ? "Rises above" : "Falls below"}
                        </td>
                        <td className="alert-price">
                          ${a.target_price.toFixed(2)}
                        </td>
                        <td className="alert-date">{formatDate(a.created_at)}</td>
                        <td>
                          <button
                            className="alert-delete-btn"
                            onClick={() => handleDelete(a.id)}
                            title="Delete alert"
                          >
                            ✕
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>

          <div className="alerts-section">
            <h2 className="alerts-section-title">Triggered Alerts</h2>
            {triggered.length === 0 ? (
              <p className="alerts-empty">No triggered alerts yet.</p>
            ) : (
              <div className="alerts-table-wrapper alerts-table-wrapper-green">
                <table className="alerts-table">
                  <thead>
                    <tr>
                      <th>Ticker</th>
                      <th>Condition</th>
                      <th>Target Price</th>
                      <th>Triggered Price</th>
                      <th>Triggered</th>
                      <th></th>
                    </tr>
                  </thead>
                  <tbody>
                    {triggered.map((a) => (
                      <tr key={a.id}>
                        <td>
                          <span className="alert-ticker-badge">{a.ticker}</span>
                        </td>
                        <td className="alert-direction">
                          {a.direction === "above" ? "Rises above" : "Falls below"}
                        </td>
                        <td className="alert-price">
                          ${a.target_price.toFixed(2)}
                        </td>
                        <td className="alert-price">
                          {a.triggered_price !== null ? `$${a.triggered_price.toFixed(2)}` : "-"}
                        </td>
                        <td className="alert-date">
                          {formatDate(a.triggered_at)}
                        </td>
                        <td>
                          <button
                            className="alert-delete-btn"
                            onClick={() => handleDelete(a.id)}
                            title="Delete alert"
                          >
                            ✕
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}