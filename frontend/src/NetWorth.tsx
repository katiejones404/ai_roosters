/*
 * NetWorth.tsx
 * Net worth tracker page where users manage manual assets and liabilities,
 * view their total financial position, and export data as CSV or PDF.
 */
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

const MAX_BALANCE = 999_999_999_999;

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

    if (balance > MAX_BALANCE) {
      setFormError("Balance cannot exceed $999,999,999,999.");
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
            ['Stock Portfolio', 'Portfolio', formatCurrency(s.portfolio_value)],
            ...s.assets.map(a => [a.name, CATEGORY_LABELS[a.category] || a.category, formatCurrency(a.balance)]),
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
                body: s.liabilities.map(l => [l.name, CATEGORY_LABELS[l.category] || l.category, formatCurrency(l.balance)]),
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
                <button
                  type="button"
                  className="nw-category-badge nw-badge-portfolio nw-portfolio-link"
                  onClick={() => navigate("/portfolio")}
                  aria-label="Go to portfolio"
                >
                  Portfolio
                </button>
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
              <label className="modal-label">Name</label>
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
              <label className="modal-label" style={{ marginTop: "0.75rem" }}>
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
              <label className="modal-label" style={{ marginTop: "0.75rem" }}>
                Balance ($)
              </label>
              <input
                className="modal-input"
                type="number"
                min="0"
                max="999999999999"
                step="0.01"
                placeholder="e.g. 5000"
                value={formBalance}
                onChange={(e) => {
                  const value = e.target.value;

                  if (value && parseFloat(value) > MAX_BALANCE) {
                    setFormError("Max allowed is $999,999,999,999.");
                    return;
                  }

                  setFormBalance(value);
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
