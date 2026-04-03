import { useState, useEffect } from "react";
import axios from "axios";
import "./Alerts.css";
import LoadingScreen from "./components/LoadingScreen";

const API_BASE = (import.meta.env.VITE_API_BASE_URL || "http://localhost:8000").replace(/\/+$/, "");

const WEBSITE_TICKERS = [
  "KSS", "ALK", "NVS", "AXP", "FCX",
  "CSX", "DAL", "NTAP", "AMZN", "AAPL",
  "MRK", "NVDA", "COP", "BHP", "EA",
];

interface Alert {
  id: string;
  ticker: string;
  target_price: number;
  direction: string;
  is_active: boolean;
  triggered_at: string | null;
  created_at: string | null;
}

function formatDate(iso: string | null): string {
  if (!iso) return "-";
  return new Date(iso).toLocaleDateString("en-US", {
    month: "short", day: "numeric", year: "numeric",
  });
}

export default function Alerts() {
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [ticker, setTicker] = useState(WEBSITE_TICKERS[0]);
  const [targetPrice, setTargetPrice] = useState("");
  const [direction, setDirection] = useState<"above" | "below">("above");
  const [creating, setCreating] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

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
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    setFormError(null);
    const price = parseFloat(targetPrice);
    if (!targetPrice || isNaN(price) || price <= 0) {
      setFormError("Enter a valid positive target price.");
      return;
    }
    setCreating(true);
    try {
      await axios.post(`${API_BASE}/api/alerts`, {
        ticker,
        target_price: price,
        direction,
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

  return (
    <div className="app-container">
      <div className="home-card alerts-card">
      <div className="alerts-header">
        <h1 className="alerts-title">Price Alerts</h1>
        <p className="alerts-subtitle">Get notified by email when a stock hits your target price</p>
      </div>

      {/* Create alert form */}
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
                {WEBSITE_TICKERS.map((t) => (
                  <option key={t} value={t}>{t}</option>
                ))}
              </select>
            </div>
            <div className="alert-field">
              <label className="alert-label">Condition</label>
              <select
                className="alert-select"
                value={direction}
                onChange={(e) => setDirection(e.target.value as "above" | "below")}
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
            <button className="alert-create-btn" type="submit" disabled={creating}>
              {creating ? "Creating..." : "+ Add Alert"}
            </button>
          </div>
          {formError && <p className="alert-form-error">{formError}</p>}
        </form>
      </div>

      {error && <p className="alerts-error">{error}</p>}

      {/* Active alerts */}
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
                    <td><span className="alert-ticker-badge">{a.ticker}</span></td>
                    <td className="alert-direction">
                      {a.direction === "above" ? "Rises above" : "Falls below"}
                    </td>
                    <td className="alert-price">${a.target_price.toFixed(2)}</td>
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

      {/* Triggered alerts */}
      {triggered.length > 0 && (
        <div className="alerts-section">
          <h2 className="alerts-section-title">Triggered Alerts</h2>
          <div className="alerts-table-wrapper">
            <table className="alerts-table alerts-table-muted">
              <thead>
                <tr>
                  <th>Ticker</th>
                  <th>Condition</th>
                  <th>Target Price</th>
                  <th>Triggered</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {triggered.map((a) => (
                  <tr key={a.id}>
                    <td><span className="alert-ticker-badge muted">{a.ticker}</span></td>
                    <td className="alert-direction muted">
                      {a.direction === "above" ? "Rises above" : "Falls below"}
                    </td>
                    <td className="alert-price muted">${a.target_price.toFixed(2)}</td>
                    <td className="alert-date">{formatDate(a.triggered_at)}</td>
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
        </div>
      )}
      </div>
    </div>
  );
}
