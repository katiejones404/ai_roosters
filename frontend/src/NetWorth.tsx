import React, { useState, useEffect } from "react";
import axios from "axios";
import { useNavigate } from "react-router-dom";
import { getToken } from "./utils/auth";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
} from "recharts";
import "./networth.css";
import LoadingScreen from "./components/LoadingScreen";
import jsPDF from 'jspdf';
import autoTable from 'jspdf-autotable';

const API_BASE = (
  import.meta.env.VITE_API_BASE_URL || "http://localhost:8000"
).replace(/\/+$/, "");

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface NetworthAsset {
  id: string;
  name: string;
  category: string;
  balance: number;
  updated_at: string | null;
}

interface NetworthLiability {
  id: string;
  name: string;
  category: string;
  balance: number;
  updated_at: string | null;
}

interface NetworthSummary {
  portfolio_value: number;
  total_assets: number;
  total_liabilities: number;
  net_worth: number;
  assets: NetworthAsset[];
  liabilities: NetworthLiability[];
}

interface SnapshotPoint {
  snapshot_date: string;
  net_worth: number;
  portfolio_value: number;
  total_assets: number;
  total_liabilities: number;
}

type ModalMode =
  | "add_asset"
  | "edit_asset"
  | "add_liability"
  | "edit_liability"
  | null;

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const ASSET_CATEGORIES = [
  { value: "cash", label: "Cash" },
  { value: "checking", label: "Checking" },
  { value: "savings", label: "Savings" },
  { value: "real_estate", label: "Real Estate" },
  { value: "vehicle", label: "Vehicle" },
  { value: "other", label: "Other" },
];

const LIABILITY_CATEGORIES = [
  { value: "credit_card", label: "Credit Card" },
  { value: "student_loan", label: "Student Loan" },
  { value: "auto_loan", label: "Auto Loan" },
  { value: "mortgage", label: "Mortgage" },
  { value: "other", label: "Other" },
];

const CATEGORY_LABELS: Record<string, string> = {
  cash: "Cash",
  checking: "Checking",
  savings: "Savings",
  real_estate: "Real Estate",
  vehicle: "Vehicle",
  other: "Other",
  credit_card: "Credit Card",
  student_loan: "Student Loan",
  auto_loan: "Auto Loan",
  mortgage: "Mortgage",
  portfolio: "Portfolio",
};

const CATEGORY_COLORS: Record<string, string> = {
  portfolio: "#6366f1",
  cash: "#10b981",
  checking: "#3b82f6",
  savings: "#f59e0b",
  real_estate: "#8b5cf6",
  vehicle: "#ec4899",
  other: "#94a3b8",
};

// ---------------------------------------------------------------------------
// Quiz constants
// ---------------------------------------------------------------------------

const QUIZ_QUESTIONS = [
  {
    id: 1,
    question: "The market drops 20% overnight. What do you do?",
    options: [
      { text: "Buy more — it's on sale!", score: 4 },
      { text: "Hold and wait it out", score: 3 },
      { text: "Sell a little to sleep at night", score: 2 },
      { text: "Sell everything immediately", score: 1 },
    ],
  },
  {
    id: 2,
    question: "What's your investment time horizon?",
    options: [
      { text: "10+ years, I'm in it for the long haul", score: 4 },
      { text: "5–10 years", score: 3 },
      { text: "2–5 years", score: 2 },
      { text: "Less than 2 years", score: 1 },
    ],
  },
  {
    id: 3,
    question: "A friend tells you about a hot new stock. You:",
    options: [
      { text: "Put in a significant chunk right away", score: 4 },
      { text: "Research it first, then invest a little", score: 3 },
      { text: "Ask a few more people before deciding", score: 2 },
      { text: "Stick to your current plan", score: 1 },
    ],
  },
  {
    id: 4,
    question: "What best describes your financial goal?",
    options: [
      { text: "Maximum growth, I can handle volatility", score: 4 },
      { text: "Growth with some stability", score: 3 },
      { text: "Stability with some growth", score: 2 },
      { text: "Preserve my capital above all", score: 1 },
    ],
  },
  {
    id: 5,
    question: "How often do you check your portfolio?",
    options: [
      { text: "Multiple times a day — I love it", score: 4 },
      { text: "Once a day or a few times a week", score: 3 },
      { text: "Once a month or so", score: 2 },
      { text: "Rarely — set it and forget it", score: 1 },
    ],
  },
];

const QUIZ_PROFILES = [
  {
    min: 17,
    max: 20,
    label: "Risk Taker 🚀",
    description:
      "You thrive on volatility and see every dip as an opportunity. You're built for high-growth, high-risk strategies — think emerging markets, small-caps, and speculative plays.",
    allocation: { stocks: 90, bonds: 5, cash: 5 },
    color: "#10b981",
    borderColor: "rgba(16, 185, 129, 0.3)",
    bg: "rgba(16, 185, 129, 0.07)",
  },
  {
    min: 13,
    max: 16,
    label: "Growth Seeker 📈",
    description:
      "You want strong returns and can stomach moderate swings. A diversified equity portfolio with some international exposure suits you well.",
    allocation: { stocks: 75, bonds: 15, cash: 10 },
    color: "#818cf8",
    borderColor: "rgba(129, 140, 248, 0.3)",
    bg: "rgba(129, 140, 248, 0.07)",
  },
  {
    min: 9,
    max: 12,
    label: "Balanced Investor ⚖️",
    description:
      "You want the best of both worlds — growth without too much heartache. A 60/40 portfolio or a target-date fund is right in your wheelhouse.",
    allocation: { stocks: 60, bonds: 30, cash: 10 },
    color: "#f59e0b",
    borderColor: "rgba(245, 158, 11, 0.3)",
    bg: "rgba(245, 158, 11, 0.07)",
  },
  {
    min: 5,
    max: 8,
    label: "Safe Player 🛡️",
    description:
      "Capital preservation is your priority. You sleep better knowing your money is protected, even if it grows more slowly.",
    allocation: { stocks: 30, bonds: 50, cash: 20 },
    color: "#64748b",
    borderColor: "rgba(100, 116, 139, 0.3)",
    bg: "rgba(100, 116, 139, 0.07)",
  },
];

// ---------------------------------------------------------------------------
// Quiz sub-components
// ---------------------------------------------------------------------------

function AllocBar({
  label,
  pct,
  color,
}: {
  label: string;
  pct: number;
  color: string;
}) {
  return (
    <div className="quiz-alloc-row">
      <div className="quiz-alloc-label">{label}</div>
      <div className="quiz-alloc-track">
        <div
          className="quiz-alloc-fill"
          style={{ width: `${pct}%`, background: color }}
        />
      </div>
      <div className="quiz-alloc-pct">{pct}%</div>
    </div>
  );
}

function InvestorQuiz() {
  const [answers, setAnswers] = useState<Record<number, number>>({});
  const [submitted, setSubmitted] = useState(false);
  const [profile, setProfile] = useState<(typeof QUIZ_PROFILES)[0] | null>(
    null,
  );

  const answer = (questionId: number, score: number) => {
    setAnswers((prev) => ({ ...prev, [questionId]: score }));
  };

  const submit = () => {
    const total = Object.values(answers).reduce((a, b) => a + b, 0);
    const found = QUIZ_PROFILES.find((p) => total >= p.min && total <= p.max);
    setProfile(found || QUIZ_PROFILES[2]);
    setSubmitted(true);
  };

  const reset = () => {
    setAnswers({});
    setSubmitted(false);
    setProfile(null);
  };

  const answered = Object.keys(answers).length;
  const progress = (answered / QUIZ_QUESTIONS.length) * 100;

  return (
    <div className="quiz-section">
      <div className="quiz-section-header">
        <h2 className="nw-section-title">Investor Personality Quiz</h2>
        <p className="quiz-section-sub">
          Find out what kind of investor you are
        </p>
      </div>

      {submitted && profile ? (
        <div className="quiz-inner">
          <div
            className="quiz-result-card"
            style={{ borderColor: profile.borderColor, background: profile.bg }}
          >
            <div className="quiz-result-label" style={{ color: profile.color }}>
              Your Profile
            </div>
            <div className="quiz-result-name" style={{ color: profile.color }}>
              {profile.label}
            </div>
            <p className="quiz-result-desc">{profile.description}</p>
            <div className="quiz-alloc-title">Suggested Allocation</div>
            <div className="quiz-alloc-bars">
              <AllocBar
                label="Stocks"
                pct={profile.allocation.stocks}
                color="#6366f1"
              />
              <AllocBar
                label="Bonds"
                pct={profile.allocation.bonds}
                color="#10b981"
              />
              <AllocBar
                label="Cash"
                pct={profile.allocation.cash}
                color="#64748b"
              />
            </div>
          </div>
          <button className="quiz-retake-btn" onClick={reset}>
            Retake Quiz
          </button>
        </div>
      ) : (
        <div className="quiz-inner">
          <div className="quiz-progress-bar-track">
            <div
              className="quiz-progress-bar-fill"
              style={{ width: `${progress}%` }}
            />
          </div>
          <div className="quiz-progress-label">
            {answered} of {QUIZ_QUESTIONS.length} answered
          </div>

          <div className="quiz-questions">
            {QUIZ_QUESTIONS.map((q) => (
              <div key={q.id} className="quiz-question-block">
                <p className="quiz-question-text">
                  <span className="quiz-q-num">{q.id}.</span> {q.question}
                </p>
                <div className="quiz-options">
                  {q.options.map((opt) => (
                    <button
                      key={opt.score}
                      className={`quiz-option-btn ${answers[q.id] === opt.score ? "selected" : ""}`}
                      onClick={() => answer(q.id, opt.score)}
                    >
                      {opt.text}
                    </button>
                  ))}
                </div>
              </div>
            ))}
          </div>

          <button
            className="quiz-submit-btn"
            disabled={answered < QUIZ_QUESTIONS.length}
            onClick={submit}
          >
            {answered < QUIZ_QUESTIONS.length
              ? `Answer all questions (${QUIZ_QUESTIONS.length - answered} left)`
              : "See My Profile →"}
          </button>
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const formatCurrency = (v: number | null | undefined) => {
  if (v === null || v === undefined) return "N/A";
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(v);
};

const formatShortDate = (iso: string) => {
  const [, m, d] = iso.split("-");
  return `${m}/${d}`;
};

// ---------------------------------------------------------------------------
// Custom tooltips
// ---------------------------------------------------------------------------

const HistoryTooltip = ({ active, payload, label }: any) => {
  if (!active || !payload?.length) return null;
  return (
    <div className="nw-chart-tooltip">
      <div className="nw-tooltip-date">{label}</div>
      <div className="nw-tooltip-value">{formatCurrency(payload[0].value)}</div>
    </div>
  );
};

const PieTooltip = ({ active, payload }: any) => {
  if (!active || !payload?.length) return null;
  const entry = payload[0];
  return (
    <div className="nw-chart-tooltip">
      <div className="nw-tooltip-date">{entry.name}</div>
      <div className="nw-tooltip-value">{formatCurrency(entry.value)}</div>
    </div>
  );
};

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

const NetWorth = () => {
  const navigate = useNavigate();

  const [summary, setSummary] = useState<NetworthSummary | null>(null);
  const [history, setHistory] = useState<SnapshotPoint[]>([]);
  const [historyRange, setHistoryRange] = useState<30 | 90 | 365>(30);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [modalMode, setModalMode] = useState<ModalMode>(null);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [formName, setFormName] = useState("");
  const [formCategory, setFormCategory] = useState("");
  const [formBalance, setFormBalance] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  const authHeaders = () => ({ Authorization: `Bearer ${getToken()}` });

  const fetchSummary = async () => {
    const token = getToken();
    if (!token) {
      navigate("/login");
      return;
    }
    try {
      setLoading(true);
      const res = await axios.get<NetworthSummary>(`${API_BASE}/api/networth`, {
        headers: authHeaders(),
      });
      setSummary(res.data);
      setError(null);
    } catch (err: any) {
      if (err.response?.status === 401) {
        navigate("/login");
        return;
      }
      setError("Failed to load net worth data.");
    } finally {
      setLoading(false);
    }
  };

  const fetchHistory = async () => {
    const token = getToken();
    if (!token) return;
    try {
      const res = await axios.get<SnapshotPoint[]>(
        `${API_BASE}/api/networth/history?days=${historyRange}`,
        { headers: authHeaders() },
      );
      setHistory(res.data);
    } catch {
      // chart stays empty on failure
    }
  };

  const recordSnapshot = async () => {
    try {
      await axios.post(`${API_BASE}/api/networth/snapshot`, null, {
        headers: authHeaders(),
      });
    } catch {
      // fire-and-forget
    }
  };

  useEffect(() => {
    fetchSummary();
    recordSnapshot();
  }, []);

  useEffect(() => {
    fetchHistory();
  }, [historyRange]);

  useEffect(() => {
    if (!loading) fetchHistory();
  }, [loading]);

  const buildPieData = () => {
    if (!summary) return [];
    const data: {
      name: string;
      value: number;
      color: string;
      category: string;
    }[] = [];
    if (summary.portfolio_value > 0) {
      data.push({
        name: "Portfolio",
        value: summary.portfolio_value,
        color: CATEGORY_COLORS.portfolio,
        category: "portfolio",
      });
    }
    const categoryTotals: Record<string, number> = {};
    for (const asset of summary.assets) {
      categoryTotals[asset.category] =
        (categoryTotals[asset.category] || 0) + asset.balance;
    }
    for (const [cat, total] of Object.entries(categoryTotals)) {
      if (total > 0) {
        data.push({
          name: CATEGORY_LABELS[cat] || cat,
          value: total,
          color: CATEGORY_COLORS[cat] || "#94a3b8",
          category: cat,
        });
      }
    }
    return data;
  };

  const openAddAsset = () => {
    setModalMode("add_asset");
    setEditingId(null);
    setFormName("");
    setFormCategory("cash");
    setFormBalance("");
    setFormError(null);
  };
  const openEditAsset = (a: NetworthAsset) => {
    setModalMode("edit_asset");
    setEditingId(a.id);
    setFormName(a.name);
    setFormCategory(a.category);
    setFormBalance(String(a.balance));
    setFormError(null);
  };
  const openAddLiability = () => {
    setModalMode("add_liability");
    setEditingId(null);
    setFormName("");
    setFormCategory("credit_card");
    setFormBalance("");
    setFormError(null);
  };
  const openEditLiability = (l: NetworthLiability) => {
    setModalMode("edit_liability");
    setEditingId(l.id);
    setFormName(l.name);
    setFormCategory(l.category);
    setFormBalance(String(l.balance));
    setFormError(null);
  };
  const closeModal = () => {
    setModalMode(null);
    setEditingId(null);
    setFormError(null);
  };

  const handleModalSubmit = async () => {
    const balance = parseFloat(formBalance);
    if (!formName.trim()) {
      setFormError("Name is required.");
      return;
    }
    if (isNaN(balance) || balance < 0) {
      setFormError("Enter a valid balance.");
      return;
    }
    setSubmitting(true);
    setFormError(null);
    try {
      const body = { name: formName.trim(), category: formCategory, balance };
      if (modalMode === "add_asset") {
        await axios.post(`${API_BASE}/api/networth/assets`, body, {
          headers: authHeaders(),
        });
      } else if (modalMode === "edit_asset" && editingId) {
        await axios.put(`${API_BASE}/api/networth/assets/${editingId}`, body, {
          headers: authHeaders(),
        });
      } else if (modalMode === "add_liability") {
        await axios.post(`${API_BASE}/api/networth/liabilities`, body, {
          headers: authHeaders(),
        });
      } else if (modalMode === "edit_liability" && editingId) {
        await axios.put(
          `${API_BASE}/api/networth/liabilities/${editingId}`,
          body,
          { headers: authHeaders() },
        );
      }
      closeModal();
      await fetchSummary();
      await recordSnapshot();
      await fetchHistory();
    } catch (err: any) {
      setFormError(err.response?.data?.detail || "Something went wrong.");
    } finally {
      setSubmitting(false);
    }
  };

  const handleDeleteAsset = async (id: string) => {
    if (!confirm("Delete this asset?")) return;
    try {
      await axios.delete(`${API_BASE}/api/networth/assets/${id}`, {
        headers: authHeaders(),
      });
      await fetchSummary();
      await recordSnapshot();
      await fetchHistory();
    } catch {
      alert("Failed to delete asset.");
    }
  };

  const handleDeleteLiability = async (id: string) => {
    if (!confirm("Delete this liability?")) return;
    try {
      await axios.delete(`${API_BASE}/api/networth/liabilities/${id}`, {
        headers: authHeaders(),
      });
      await fetchSummary();
      await recordSnapshot();
      await fetchHistory();
    } catch {
      alert("Failed to delete liability.");
    }
  };

    const handleExportCSVNW = () => {
        if (!summary) return;
        const s = summary;
        const rows: string[][] = [['Section', 'Name', 'Category', 'Balance']];
        rows.push(['Assets', 'Stock Portfolio', 'Portfolio', s.portfolio_value.toFixed(2)]);
        s.assets.forEach(a => rows.push(['Assets', a.name, CATEGORY_LABELS[a.category] || a.category, a.balance.toFixed(2)]));
        s.liabilities.forEach(l => rows.push(['Liabilities', l.name, CATEGORY_LABELS[l.category] || l.category, l.balance.toFixed(2)]));
        rows.push(['', 'Total Assets', '', s.total_assets.toFixed(2)]);
        rows.push(['', 'Total Liabilities', '', s.total_liabilities.toFixed(2)]);
        rows.push(['', 'Net Worth', '', s.net_worth.toFixed(2)]);
        const csv = rows.map(r => r.join(',')).join('\n');
        const blob = new Blob([csv], { type: 'text/csv' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url; a.download = 'networth.csv'; a.click();
        URL.revokeObjectURL(url);
    };

    const handleExportPDFNW = () => {
        if (!summary) return;
        const s = summary;
        const doc = new jsPDF();
        doc.setFontSize(18);
        doc.text('Net Worth Report', 14, 22);
        doc.setFontSize(10);
        doc.setTextColor(120, 120, 120);
        doc.text(`Generated: ${new Date().toLocaleDateString()}`, 14, 30);
        doc.setTextColor(0, 0, 0);
        doc.setFontSize(12);
        doc.text('Summary', 14, 40);
        doc.setFontSize(10);
        doc.text(`Net Worth: ${formatCurrency(s.net_worth)}`, 14, 48);
        doc.text(`Portfolio Value: ${formatCurrency(s.portfolio_value)}`, 14, 56);
        doc.text(`Total Assets: ${formatCurrency(s.total_assets)}`, 14, 64);
        doc.text(`Total Liabilities: ${formatCurrency(s.total_liabilities)}`, 14, 72);
        const assetRows = [
            ['Stock Portfolio', 'Portfolio', `$${s.portfolio_value.toFixed(2)}`],
            ...s.assets.map(a => [a.name, CATEGORY_LABELS[a.category] || a.category, `$${a.balance.toFixed(2)}`]),
        ];
        autoTable(doc, {
            head: [['Asset', 'Category', 'Balance']],
            body: assetRows,
            startY: 80,
            styles: { fontSize: 9 },
            headStyles: { fillColor: [16, 185, 129] },
        });
        if (s.liabilities.length > 0) {
            const finalY = (doc as any).lastAutoTable.finalY + 10;
            autoTable(doc, {
                head: [['Liability', 'Category', 'Balance']],
                body: s.liabilities.map(l => [l.name, CATEGORY_LABELS[l.category] || l.category, `$${l.balance.toFixed(2)}`]),
                startY: finalY,
                styles: { fontSize: 9 },
                headStyles: { fillColor: [239, 68, 68] },
            });
        }
        doc.save('networth.pdf');
    };

  if (loading) {
    return (
      <div className="app-container">
        <div className="home-background-shapes">
          <div className="home-shape home-shape-1"></div>
          <div className="home-shape home-shape-2"></div>
          <div className="home-shape home-shape-3"></div>
        </div>
        <div className="home-card">
          <LoadingScreen message="Loading net worth..." />
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="app-container">
        <div className="home-background-shapes">
          <div className="home-shape home-shape-1"></div>
          <div className="home-shape home-shape-2"></div>
          <div className="home-shape home-shape-3"></div>
        </div>
        <div className="home-card">
          <div className="portfolio-error">
            <p className="sentiment-error">{error}</p>
            <button onClick={fetchSummary} className="retry-button">
              Retry
            </button>
          </div>
        </div>
      </div>
    );
  }

  const s = summary!;
  const netWorthPositive = s.net_worth >= 0;
  const pieData = buildPieData();
  const totalPieValue = pieData.reduce((sum, d) => sum + d.value, 0);
  const isAddingAsset = modalMode === "add_asset" || modalMode === "edit_asset";
  const categories = isAddingAsset ? ASSET_CATEGORIES : LIABILITY_CATEGORIES;
  const modalTitle =
    modalMode === "add_asset"
      ? "Add Asset"
      : modalMode === "edit_asset"
        ? "Edit Asset"
        : modalMode === "add_liability"
          ? "Add Liability"
          : "Edit Liability";

  return (
    <div className="app-container">
      <div className="home-background-shapes">
        <div className="home-shape home-shape-1"></div>
        <div className="home-shape home-shape-2"></div>
        <div className="home-shape home-shape-3"></div>
      </div>

            <div className="home-card nw-card">
                <div className="home-content">

                    {/* Header */}
                    <div className="nw-header">
                        <div>
                            <h1>Net Worth</h1>
                            <p>Your complete financial picture</p>
                        </div>
                        <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
                            <button className="csv-export-btn" onClick={handleExportCSVNW}>Export CSV</button>
                            <button className="csv-export-btn" onClick={handleExportPDFNW}>Export PDF</button>
                        </div>
                    </div>

          {/* Summary stat cards */}
          <div className="nw-summary-grid">
            <div
              className={`nw-stat-card nw-stat-primary ${netWorthPositive ? "positive" : "negative"}`}
            >
              <div className="nw-stat-label">Net Worth</div>
              <div
                className={`nw-stat-value nw-stat-large ${netWorthPositive ? "positive" : "negative"}`}
              >
                {formatCurrency(s.net_worth)}
              </div>
              <div className="nw-stat-sub">
                {netWorthPositive
                  ? "Assets exceed liabilities"
                  : "Liabilities exceed assets"}
              </div>
            </div>
            <div className="nw-stat-card">
              <div className="nw-stat-label">Portfolio</div>
              <div className="nw-stat-value">
                {formatCurrency(s.portfolio_value)}
              </div>
            </div>
            <div className="nw-stat-card">
              <div className="nw-stat-label">Total Assets</div>
              <div className="nw-stat-value positive">
                {formatCurrency(s.total_assets)}
              </div>
            </div>
            <div className="nw-stat-card">
              <div className="nw-stat-label">Total Liabilities</div>
              <div
                className={`nw-stat-value ${s.total_liabilities > 0 ? "negative" : ""}`}
              >
                {formatCurrency(s.total_liabilities)}
              </div>
            </div>
          </div>

          {/* Charts row */}
          <div className="nw-charts-row">
            <div className="nw-chart-card nw-history-chart">
              <div className="nw-chart-header">
                <h3 className="nw-chart-title">Net Worth Over Time</h3>
                <div className="nw-range-btns">
                  {([30, 90, 365] as const).map((r) => (
                    <button
                      key={r}
                      className={historyRange === r ? "active" : ""}
                      onClick={() => setHistoryRange(r)}
                    >
                      {r === 365 ? "1Y" : `${r}D`}
                    </button>
                  ))}
                </div>
              </div>
              {history.length >= 2 ? (
                <ResponsiveContainer width="100%" height={200}>
                  <LineChart
                    data={history}
                    margin={{ top: 8, right: 8, left: -10, bottom: 0 }}
                  >
                    <CartesianGrid
                      strokeDasharray="3 3"
                      stroke="rgba(255,255,255,0.07)"
                    />
                    <XAxis
                      dataKey="snapshot_date"
                      tickFormatter={formatShortDate}
                      tick={{ fontSize: 10, fill: "#94a3b8" }}
                      interval={Math.max(0, Math.floor(history.length / 5) - 1)}
                    />
                    <YAxis
                      tick={{ fontSize: 10, fill: "#94a3b8" }}
                      tickFormatter={(v: number) =>
                        `$${(v / 1000).toFixed(0)}k`
                      }
                    />
                    <Tooltip content={<HistoryTooltip />} />
                    <Line
                      type="monotone"
                      dataKey="net_worth"
                      stroke={netWorthPositive ? "#10b981" : "#ef4444"}
                      strokeWidth={2}
                      dot={false}
                    />
                  </LineChart>
                </ResponsiveContainer>
              ) : (
                <div className="nw-chart-empty">
                  Net worth history will appear here after multiple daily
                  visits.
                </div>
              )}
            </div>

            <div className="nw-chart-card nw-donut-card">
              <div className="nw-chart-header">
                <h3 className="nw-chart-title">Asset Distribution</h3>
              </div>
              {pieData.length > 0 ? (
                <>
                  <ResponsiveContainer width="100%" height={190}>
                    <PieChart>
                      <Pie
                        data={pieData}
                        cx="50%"
                        cy="50%"
                        innerRadius={55}
                        outerRadius={85}
                        paddingAngle={2}
                        dataKey="value"
                      >
                        {pieData.map((entry, i) => (
                          <Cell key={`cell-${i}`} fill={entry.color} />
                        ))}
                      </Pie>
                      <Tooltip content={<PieTooltip />} />
                    </PieChart>
                  </ResponsiveContainer>
                  <div className="nw-pie-legend">
                    {pieData.map((entry) => (
                      <div key={entry.category} className="nw-pie-legend-row">
                        <span
                          className="nw-pie-dot"
                          style={{ background: entry.color }}
                        />
                        <span className="nw-pie-label">{entry.name}</span>
                        <span className="nw-pie-pct">
                          {totalPieValue > 0
                            ? `${((entry.value / totalPieValue) * 100).toFixed(1)}%`
                            : "0%"}
                        </span>
                        <span className="nw-pie-amount">
                          {formatCurrency(entry.value)}
                        </span>
                      </div>
                    ))}
                  </div>
                </>
              ) : (
                <div className="nw-chart-empty">
                  Add assets to see distribution.
                </div>
              )}
            </div>
          </div>

          {/* Assets + Liabilities */}
          <div className="nw-lists-row">
            <div className="nw-list-section">
              <div className="nw-list-header">
                <h2 className="nw-section-title">Assets</h2>
                <button className="add-shares-btn" onClick={openAddAsset}>
                  + Add Asset
                </button>
              </div>
              <div className="nw-entry-row nw-portfolio-row">
                <span className="nw-category-badge nw-badge-portfolio">
                  Portfolio
                </span>
                <span className="nw-entry-name">Stock Portfolio</span>
                <span className="nw-entry-balance positive">
                  {formatCurrency(s.portfolio_value)}
                </span>
                <div className="nw-entry-actions" />
              </div>
              {s.assets.length === 0 && (
                <div className="nw-empty-hint">
                  No manual assets yet. Click "+ Add Asset" to start.
                </div>
              )}
              {s.assets.map((a) => (
                <div key={a.id} className="nw-entry-row">
                  <span className="nw-category-badge">
                    {CATEGORY_LABELS[a.category] || a.category}
                  </span>
                  <span className="nw-entry-name">{a.name}</span>
                  <span className="nw-entry-balance">
                    {formatCurrency(a.balance)}
                  </span>
                  <div className="nw-entry-actions">
                    <button
                      className="nw-edit-btn"
                      onClick={() => openEditAsset(a)}
                    >
                      Edit
                    </button>
                    <button
                      className="nw-delete-btn"
                      onClick={() => handleDeleteAsset(a.id)}
                    >
                      ✕
                    </button>
                  </div>
                </div>
              ))}
              <div className="nw-total-row">
                <span className="nw-total-label">Total Assets</span>
                <span className="nw-total-value positive">
                  {formatCurrency(s.total_assets)}
                </span>
              </div>
            </div>

            <div className="nw-list-section">
              <div className="nw-list-header">
                <h2 className="nw-section-title">Liabilities</h2>
                <button className="add-shares-btn" onClick={openAddLiability}>
                  + Add Liability
                </button>
              </div>
              {s.liabilities.length === 0 && (
                <div className="nw-empty-hint">
                  No liabilities tracked. Click "+ Add Liability" to add one.
                </div>
              )}
              {s.liabilities.map((l) => (
                <div key={l.id} className="nw-entry-row">
                  <span className="nw-category-badge nw-badge-liability">
                    {CATEGORY_LABELS[l.category] || l.category}
                  </span>
                  <span className="nw-entry-name">{l.name}</span>
                  <span className="nw-entry-balance negative">
                    {formatCurrency(l.balance)}
                  </span>
                  <div className="nw-entry-actions">
                    <button
                      className="nw-edit-btn"
                      onClick={() => openEditLiability(l)}
                    >
                      Edit
                    </button>
                    <button
                      className="nw-delete-btn"
                      onClick={() => handleDeleteLiability(l.id)}
                    >
                      ✕
                    </button>
                  </div>
                </div>
              ))}
              <div className="nw-total-row">
                <span className="nw-total-label">Total Liabilities</span>
                <span
                  className={`nw-total-value ${s.total_liabilities > 0 ? "negative" : ""}`}
                >
                  {formatCurrency(s.total_liabilities)}
                </span>
              </div>
            </div>
          </div>

          {/* Investor Personality Quiz */}
          <InvestorQuiz />
        </div>
      </div>

      {/* Add / Edit Modal */}
      {modalMode && (
        <div
          className="modal-backdrop"
          onClick={(e) => e.target === e.currentTarget && closeModal()}
        >
          <div className="modal-container nw-modal">
            <div className="modal-header">
              <h2>{modalTitle}</h2>
              <button className="modal-close-btn" onClick={closeModal}>
                x
              </button>
            </div>
            <div className="modal-body">
              <label className="modal-labe">Name</label>
              <input
                className="modal-input"
                type="text"
                placeholder={
                  isAddingAsset ? "e.g. Chase Savings" : "e.g. Visa Credit Card"
                }
                value={formName}
                onChange={(e) => {
                  setFormName(e.target.value);
                  setFormError(null);
                }}
              />
              <label className="modal-labe" style={{ marginTop: "0.75rem" }}>
                Category
              </label>
              <select
                className="modal-input nw-select"
                value={formCategory}
                onChange={(e) => setFormCategory(e.target.value)}
              >
                {categories.map((c) => (
                  <option key={c.value} value={c.value}>
                    {c.label}
                  </option>
                ))}
              </select>
              <label className="modal-labe" style={{ marginTop: "0.75rem" }}>
                Balance ($)
              </label>
              <input
                className="modal-input"
                type="number"
                min="0"
                step="0.01"
                placeholder="e.g. 5000"
                value={formBalance}
                onChange={(e) => {
                  setFormBalance(e.target.value);
                  setFormError(null);
                }}
                onKeyDown={(e) => e.key === "Enter" && handleModalSubmit()}
              />
              {formError && <p className="modal-error">{formError}</p>}
            </div>
            <div className="modal-footer">
              <button
                className="modal-cancel-btn"
                onClick={closeModal}
                disabled={submitting}
              >
                Cancel
              </button>
              <button
                className="modal-confirm-btn"
                onClick={handleModalSubmit}
                disabled={submitting}
              >
                {submitting ? "Saving..." : "Save"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default NetWorth;
