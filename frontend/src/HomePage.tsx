/*
 * HomePage.tsx
 * Home page displayed after login, showing the user's portfolio summary,
 * active price alerts, investor personality quiz, and daily finance fact.
 */
import { useState, useEffect } from "react";
import { Link } from "react-router-dom";
import axios from "axios";
import { FaCaretUp, FaCaretDown } from "react-icons/fa";
import InvestorQuiz from "./components/InvestorQuiz";
import FunFinanceFacts from "./components/FunFinanceFacts";
import StreakTracker from "./components/StreakTracker";
import { getToken } from "./utils/auth";
import WhatIfCalculator from "./components/WhatIfCalculator";
import "./HomePage.css";

const API_BASE = (
  import.meta.env.VITE_API_BASE_URL || "http://localhost:8000"
).replace(/\/+$/, "");

interface PortfolioItem {
  ticker: string;
  current_price: number | null;
  return_1d: number | null;
  total_gain_loss: number | null;
  gain_loss_pct: number | null;
}

interface Alert {
  id: string;
  ticker: string;
  target_price: number;
  direction: string;
  is_active: boolean;
}

function fmtPct(v: number | null): string {
  if (v === null || v === undefined) return "N/A";
  const pct = v * 100;
  return `${pct >= 0 ? "+" : ""}${pct.toFixed(2)}%`;
}

function fmtDollar(v: number | null): string {
  if (v === null || v === undefined) return "N/A";
  return `${v >= 0 ? "+" : "-"}$${Math.abs(v).toFixed(2)}`;
}

export default function HomePage() {
  const [items, setItems] = useState<PortfolioItem[]>([]);
  const [alerts, setAlerts] = useState<Alert[]>([]);

  useEffect(() => {
    const token = getToken();
    if (!token) return;

    axios
      .get(`${API_BASE}/api/portfolio/stats/summary`, {
        headers: { Authorization: `Bearer ${token}` },
      })
      .then((res) => setItems((res.data.portfolio_items || []).slice(0, 6)))
      .catch(() => {});

    axios
      .get<Alert[]>(`${API_BASE}/api/alerts`)
      .then((res) => setAlerts(res.data.filter((a) => a.is_active).slice(0, 5)))
      .catch(() => {});
  }, []);

  return (
    <div className="hp-page">
      <div className="hp-layout">
        <div className="hp-content">
          <div className="hp-main-grid">
            <div className="hp-section hp-top-card hp-portfolio-card">
              <div className="hp-section-header">
                <h2 className="hp-section-title">Portfolio Summary</h2>
                <Link to="/portfolio" className="hp-view-link">
                  View Full -&gt;
                </Link>
              </div>

              {items.length > 0 ? (
                <div className="hp-table-wrapper">
                  <table className="hp-table">
                    <thead>
                      <tr>
                        <th>Ticker</th>
                        <th>Price</th>
                        <th>1D</th>
                        <th>Gain / Loss</th>
                      </tr>
                    </thead>
                    <tbody>
                      {items.map((item) => (
                        <tr key={item.ticker}>
                          <td>
                            <div className="hp-ticker-cell">
                              {item.return_1d !== null && (
                                <span className={item.return_1d >= 0 ? "hp-trend-up" : "hp-trend-down"}>
                                  {item.return_1d >= 0 ? <FaCaretUp /> : <FaCaretDown />}
                                </span>
                              )}
                              <Link
                                to={`/stock/${encodeURIComponent(item.ticker)}`}
                                className={`hp-ticker-link ${
                                  item.return_1d != null
                                    ? item.return_1d >= 0
                                      ? "hp-ticker-link-up"
                                      : "hp-ticker-link-down"
                                    : ""
                                }`}
                              >
                                {item.ticker}
                              </Link>
                            </div>
                          </td>
                          <td>
                            {item.current_price != null
                              ? `$${item.current_price.toFixed(2)}`
                              : "N/A"}
                          </td>
                          <td
                            className={
                              item.return_1d != null
                                ? item.return_1d >= 0
                                  ? "hp-positive"
                                  : "hp-negative"
                                : ""
                            }
                          >
                            {fmtPct(item.return_1d)}
                          </td>
                          <td
                            className={
                              item.total_gain_loss != null
                                ? item.total_gain_loss >= 0
                                  ? "hp-positive"
                                  : "hp-negative"
                                : ""
                            }
                          >
                            {fmtDollar(item.total_gain_loss)}
                            {item.gain_loss_pct != null && (
                              <span className="hp-pct">
                                {" "}
                                ({item.gain_loss_pct >= 0 ? "+" : ""}
                                {item.gain_loss_pct.toFixed(1)}%)
                              </span>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <p className="hp-empty">
                  No holdings yet.{" "}
                  <Link to="/dashboard">Browse Stocks -&gt;</Link>
                </p>
              )}
            </div>

            <div className="hp-section hp-top-card hp-alert-card">
              <div className="hp-section-header">
                <h2 className="hp-section-title">Active Alerts</h2>
                <Link to="/alerts" className="hp-view-link">
                  View All -&gt;
                </Link>
              </div>

              {alerts.length > 0 ? (
                <div className="hp-alerts-list">
                  {alerts.map((a) => (
                    <div key={a.id} className="hp-alert-row">
                      <span className="hp-alert-ticker">{a.ticker}</span>
                      <span className="hp-alert-condition">
                        {a.direction === "above"
                          ? "Rises above"
                          : "Falls below"}
                      </span>
                      <span className="hp-alert-price">
                        ${a.target_price.toFixed(2)}
                      </span>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="hp-empty">
                  No active alerts. <Link to="/alerts">Create one -&gt;</Link>
                </p>
              )}
            </div>

            <div className="hp-quiz-cell">
              <InvestorQuiz />
            </div>

            <div className="hp-fact-cell">
              <FunFinanceFacts />
              <WhatIfCalculator />
            </div>
          </div>
        </div>

        <aside className="hp-sidebar">
          <StreakTracker />
        </aside>
      </div>
    </div>
  );
}
