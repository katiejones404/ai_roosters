import { useState, useEffect, type FormEvent } from "react";
import axios from "axios";
import "./Alerts.css";
import LoadingScreen from "./components/LoadingScreen";

const API_BASE = (
  import.meta.env.VITE_API_BASE_URL || "http://localhost:8000"
).replace(/\/+$/, "");

const WEBSITE_TICKERS = [
  "KSS",
  "ALK",
  "NVS",
  "AXP",
  "FCX",
  "CSX",
  "DAL",
  "NTAP",
  "AMZN",
  "AAPL",
  "MRK",
  "NVDA",
  "COP",
  "BHP",
  "EA",
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

interface StreakData {
  currentStreak: number;
  bestStreak: number;
  lastVisit: string;
  visitDays: string[];
  totalVisits: number;
}

const STREAK_STORAGE_KEY = "stocksense_streak";

function formatDate(iso: string | null): string {
  if (!iso) return "-";
  return new Date(iso).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

function getTodayStr() {
  return new Date().toISOString().split("T")[0];
}

function loadStreak(): StreakData | null {
  try {
    const raw = localStorage.getItem(STREAK_STORAGE_KEY);
    if (!raw) return null;
    return JSON.parse(raw) as StreakData;
  } catch {
    return null;
  }
}

function saveStreak(data: StreakData) {
  localStorage.setItem(STREAK_STORAGE_KEY, JSON.stringify(data));
}

function getLastNDays(n: number) {
  const days: string[] = [];
  for (let i = n - 1; i >= 0; i--) {
    const d = new Date();
    d.setDate(d.getDate() - i);
    days.push(d.toISOString().split("T")[0]);
  }
  return days;
}

function formatShortDate(dateStr: string) {
  return new Date(`${dateStr}T00:00:00`).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
  });
}

function StreakTracker() {
  const [streakData, setStreakData] = useState<StreakData | null>(null);

  useEffect(() => {
    const today = getTodayStr();
    let data = loadStreak();

    if (!data) {
      data = {
        currentStreak: 1,
        bestStreak: 1,
        lastVisit: today,
        visitDays: [today],
        totalVisits: 1,
      };
      saveStreak(data);
    } else {
      const last = new Date(data.lastVisit);
      const now = new Date(today);
      const diffDays = Math.round(
        (now.getTime() - last.getTime()) / (1000 * 60 * 60 * 24),
      );

      if (diffDays === 1) {
        data.currentStreak += 1;
        data.bestStreak = Math.max(data.bestStreak, data.currentStreak);
        data.lastVisit = today;
        data.totalVisits += 1;
        if (!data.visitDays.includes(today)) data.visitDays.push(today);
      } else if (diffDays > 1) {
        data.currentStreak = 1;
        data.lastVisit = today;
        data.totalVisits += 1;
        if (!data.visitDays.includes(today)) data.visitDays.push(today);
      }

      saveStreak(data);
    }

    setStreakData(data);
  }, []);

  if (!streakData) return null;

  const visitSet = new Set(streakData.visitDays);
  const last28 = getLastNDays(28);

  const streakEmoji =
    streakData.currentStreak >= 30
      ? "🔥🔥🔥"
      : streakData.currentStreak >= 14
        ? "🔥🔥"
        : streakData.currentStreak >= 7
          ? "🔥"
          : streakData.currentStreak >= 3
            ? "⚡"
            : "✨";

  const streakMessage =
    streakData.currentStreak >= 30
      ? "Legendary streak! You're unstoppable."
      : streakData.currentStreak >= 14
        ? "Two weeks strong. Serious dedication."
        : streakData.currentStreak >= 7
          ? "One week streak! Keep it going."
          : streakData.currentStreak >= 3
            ? "You're building a habit — nice!"
            : "Great start! Come back tomorrow.";

  return (
    <div className="streak-card" aria-label="Streak tracker">
      <div className="streak-card-sheen" />

      <div className="streak-header">
        <div>
          <h2 className="streak-title">Streak Tracker</h2>
          <p className="streak-subtitle">Your daily login consistency</p>
        </div>
        <div className="streak-badge-pill">Live habit pulse</div>
      </div>

      <div className="streak-main-row">
        <div className="streak-primary-box">
          <div className="streak-emoji">{streakEmoji}</div>
          <div className="streak-number">{streakData.currentStreak}</div>
          <div className="streak-days-label">day streak</div>
          <div className="streak-message">{streakMessage}</div>
          <div className="streak-cta">Keep the momentum going</div>
        </div>

        <div className="streak-stats-col">
          <div className="streak-stat-box">
            <div className="streak-stat-label">🏆 Best Streak</div>
            <div className="streak-stat-val">{streakData.bestStreak} days</div>
          </div>
          <div className="streak-stat-box">
            <div className="streak-stat-label">📅 Total Visits</div>
            <div className="streak-stat-val">{streakData.totalVisits}</div>
          </div>
          <div className="streak-stat-box">
            <div className="streak-stat-label">📆 Last Visit</div>
            <div className="streak-stat-val">
              {formatShortDate(streakData.lastVisit)}
            </div>
          </div>
        </div>
      </div>

      <div className="streak-heatmap-card">
        <div className="streak-heatmap-title">Last 28 Days</div>
        <div className="streak-heatmap-grid">
          {last28.map((day) => {
            const visited = visitSet.has(day);
            const isToday = day === getTodayStr();
            return (
              <div
                key={day}
                className={`streak-dot ${visited ? "visited" : ""} ${isToday ? "today" : ""}`}
                title={`${formatShortDate(day)}${visited ? " ✓" : ""}`}
              />
            );
          })}
        </div>
        <div className="streak-heatmap-legend">
          <div className="streak-legend-item">
            <div className="streak-dot visited small" /> Visited
          </div>
          <div className="streak-legend-item">
            <div className="streak-dot small" /> Missed
          </div>
          <div className="streak-legend-item">
            <div className="streak-dot today small" /> Today
          </div>
        </div>
      </div>

      <div className="streak-milestones">
        <div className="streak-milestones-title">Milestones</div>
        <div className="streak-badges-row">
          {[
            { days: 3, label: "3-Day", emoji: "✨" },
            { days: 7, label: "1 Week", emoji: "⚡" },
            { days: 14, label: "2 Weeks", emoji: "🔥" },
            { days: 30, label: "1 Month", emoji: "🔥🔥" },
            { days: 60, label: "2 Months", emoji: "🔥🔥🔥" },
          ].map((m) => {
            const unlocked = streakData.bestStreak >= m.days;
            return (
              <div
                key={m.days}
                className={`streak-badge ${unlocked ? "unlocked" : "locked"}`}
              >
                <div className="streak-badge-emoji">
                  {unlocked ? m.emoji : "🔒"}
                </div>
                <div className="streak-badge-label">{m.label}</div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
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

  const handleCreate = async (e: FormEvent) => {
    e.preventDefault();
    setFormError(null);
    const price = parseFloat(targetPrice);
    if (!targetPrice || Number.isNaN(price) || price <= 0) {
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
          <p className="alerts-subtitle">
            Get notified by email when a stock hits your target price
          </p>
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
                  {WEBSITE_TICKERS.map((t) => (
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
                        {a.direction === "above"
                          ? "Rises above"
                          : "Falls below"}
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
                      <td>
                        <span className="alert-ticker-badge muted">
                          {a.ticker}
                        </span>
                      </td>
                      <td className="alert-direction muted">
                        {a.direction === "above"
                          ? "Rises above"
                          : "Falls below"}
                      </td>
                      <td className="alert-price muted">
                        ${a.target_price.toFixed(2)}
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
          </div>
        )}

        <div className="alerts-section">
          <StreakTracker />
        </div>
      </div>
    </div>
  );
}
