import React, { useState, useEffect } from "react";
import axios from "axios";
import { useNavigate, Link } from "react-router-dom";
import { getToken } from "./utils/auth";
import {
    BarChart, Bar, XAxis, YAxis, Tooltip,
    LineChart, Line, AreaChart, Area,
    CartesianGrid, ResponsiveContainer, Cell, Legend,
} from "recharts";
import AddToPortfolioModal from "./components/AddToPortfolio";
import LoadingScreen from "./components/LoadingScreen";
import jsPDF from 'jspdf';
import autoTable from 'jspdf-autotable';
import './portfolio.css';

const API_BASE = (import.meta.env.VITE_API_BASE_URL || "http://localhost:8000").replace(/\/+$/, "");

interface PortfolioItemWithMetrics {
    id: string;
    ticker: string;
    quantity: number;
    avg_price: number;
    current_price: number | null;
    cost_basis: number;
    current_value: number;
    total_gain_loss: number;
    gain_loss_pct: number;
    return_1d: number | null;
    return_30d: number | null;
    return_120d: number | null;
    return_360d: number | null;
    added_at: string | null;
}

interface PortfolioSummary {
    total_cost_basis: number;
    total_current_value: number;
    total_gain_loss: number;
    total_gain_loss_pct: number;
    num_positions: number;
}

interface PortfolioData {
    portfolio_items: PortfolioItemWithMetrics[];
    summary: PortfolioSummary;
}

interface PricePoint {
    date: string;
    close: number;
}

const CHART_COLORS = ['#6366f1', '#f59e0b', '#10b981', '#ec4899', '#06b6d4', '#f97316'];

/*
AnimatedValue

Counts up from 0 to the target value on mount using requestAnimationFrame.
Used in the portfolio summary stat cards for a polished entry animation.

Notes
-----
Uses easeOutCubic easing so the animation starts fast and decelerates smoothly.
*/
const AnimatedValue: React.FC<{
    value: number;
    format?: 'currency' | 'integer';
    duration?: number;
}> = ({ value, format = 'currency', duration = 1200 }) => {
    const [display, setDisplay] = useState(0);
    useEffect(() => {
        if (!value) { setDisplay(0); return; }
        const start = performance.now();
        let rafId: number;
        const step = (now: number) => {
            const elapsed = now - start;
            const progress = Math.min(elapsed / duration, 1);
            const eased = 1 - Math.pow(1 - progress, 3);
            setDisplay(value * eased);
            if (progress < 1) rafId = requestAnimationFrame(step);
            else setDisplay(value);
        };
        rafId = requestAnimationFrame(step);
        return () => cancelAnimationFrame(rafId);
    }, [value, duration]);
    if (format === 'integer') return <>{Math.round(display)}</>;
    return <>{new Intl.NumberFormat('en-US', {
        style: 'currency', currency: 'USD',
        minimumFractionDigits: 2, maximumFractionDigits: 2,
    }).format(display)}</>;
};

const Portfolio = () => {
    const navigate = useNavigate();
    const [portfolioData, setPortfolioData] = useState<PortfolioData | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [compareMode, setCompareMode] = useState(false);
    const [selectedTickers, setSelectedTickers] = useState<string[]>([]);
    const [compareData, setCompareData] = useState<Record<string, PricePoint[]>>({});
    const [compareView, setCompareView] = useState<'pct' | 'price'>('pct');
    const [compareRange, setCompareRange] = useState<'30' | '120' | '360'>('30');
    const [compareLoading, setCompareLoading] = useState(false);
    const [actionTicker, setActionTicker] = useState<string | null>(null);
    const [sellQty, setSellQty] = useState<string>('');
    const [actionError, setActionError] = useState<string | null>(null);
    const [addSharesTicker, setAddSharesTicker] = useState<string | null>(null);
    const [addSharesPrice, setAddSharesPrice] = useState<number>(0);

    useEffect(() => {
        fetchPortfolioSummary();
    }, []);

    // Fetch price history whenever selected tickers change (compare mode on)
    useEffect(() => {
        if (!compareMode || selectedTickers.length < 2) {
            setCompareData({});
            return;
        }
        const fetchPriceData = async () => {
            setCompareLoading(true);
            try {
                const token = getToken();
                const results = await Promise.all(
                    selectedTickers.map((ticker: string) =>
                        axios.get<PricePoint[]>(
                            `${API_BASE}/api/stocks/${encodeURIComponent(ticker)}/prices`,
                            { headers: { Authorization: `Bearer ${token}` } }
                        )
                    )
                );
                const newData: Record<string, PricePoint[]> = {};
                selectedTickers.forEach((ticker: string, i: number) => {
                    newData[ticker] = results[i].data;
                });
                setCompareData(newData);
            } catch {
                // price fetch failed silently; chart will show empty
            } finally {
                setCompareLoading(false);
            }
        };
        fetchPriceData();
    }, [selectedTickers, compareMode]);

    const fetchPortfolioSummary = async () => {
        try {
            setLoading(true);
            const token = getToken();
            if (!token) {
                navigate('/dashboard');
                return;
            }
            const response = await axios.get(`${API_BASE}/api/portfolio/stats/summary`, {
                headers: { Authorization: `Bearer ${token}` }
            });
            setPortfolioData(response.data);
            setError(null);
        } catch (err: unknown) {
            const axiosErr = err as { response?: { status?: number } };
            if (axiosErr.response?.status === 404) {
                setPortfolioData({
                    portfolio_items: [],
                    summary: {
                        total_cost_basis: 0,
                        total_current_value: 0,
                        total_gain_loss: 0,
                        num_positions: 0,
                        total_gain_loss_pct: 0
                    }
                });
                setError(null);
            } else if (axiosErr.response?.status === 401) {
                navigate('/dashboard');
            } else {
                setError('Failed to load portfolio data');
            }
        } finally {
            setLoading(false);
        }
    };

    const openActionPanel = (ticker: string) => {
        setActionTicker(ticker);
        setSellQty('');
        setActionError(null);
    };

    const closeActionPanel = () => {
        setActionTicker(null);
        setSellQty('');
        setActionError(null);
    };

    const removeStock = async (ticker: string) => {
        try {
            const token = getToken();
            await axios.delete(`${API_BASE}/api/portfolio/${ticker}`, {
                headers: { Authorization: `Bearer ${token}` }
            });
            setSelectedTickers(prev => prev.filter(t => t !== ticker));
            closeActionPanel();
            fetchPortfolioSummary();
        } catch {
            setActionError('Failed to remove position. Please try again.');
        }
    };

    const sellShares = async (ticker: string, currentQty: number) => {
        const qty = parseFloat(sellQty);
        if (isNaN(qty) || qty <= 0) {
            setActionError('Enter a valid number of shares to sell.');
            return;
        }
        try {
            const token = getToken();
            if (qty >= currentQty) {
                await axios.delete(`${API_BASE}/api/portfolio/${ticker}`, {
                    headers: { Authorization: `Bearer ${token}` }
                });
                setSelectedTickers((prev: string[]) => prev.filter((t: string) => t !== ticker));
            } else {
                await axios.put(
                    `${API_BASE}/api/portfolio/${ticker}`,
                    { quantity: parseFloat((currentQty - qty).toFixed(6)) },
                    { headers: { Authorization: `Bearer ${token}` } }
                );
            }
            closeActionPanel();
            fetchPortfolioSummary();
        } catch {
            setActionError('Failed to update position. Please try again.');
        }
    };

    const toggleCompareMode = () => {
        setCompareMode(prev => !prev);
        setSelectedTickers([]);
    };

    const toggleTickerSelection = (ticker: string) => {
        setSelectedTickers(prev =>
            prev.includes(ticker) ? prev.filter(t => t !== ticker) : [...prev, ticker]
        );
    };

    const formatCurrency = (value: number | null) => {
        if (value === null || value === undefined) return 'N/A';
        return new Intl.NumberFormat('en-US', {
            style: 'currency',
            currency: 'USD',
            minimumFractionDigits: 2,
            maximumFractionDigits: 2
        }).format(value);
    };

    const formatPercent = (value: number | null) => {
        if (value === null || value === undefined) return 'N/A';
        const sign = value >= 0 ? '+' : '';
        return `${sign}${value.toFixed(2)}%`;
    };

    const getReturnColor = (value: number | null): string => {
        if (value === null || value === undefined) return '';
        return value >= 0 ? 'positive' : 'negative';
    };

    const getReturnIndicator = (value: number | null): string => {
        if (value === null || value === undefined) return '-';
        return value >= 0 ? '▲' : '▼';
    };

    // Get the first/last dates from the current chart slice (YYYY-MM-DD -> MM/DD/YYYY)
    const getChartDateRange = (): { start: string; end: string } | null => {
        const tickers = Object.keys(compareData);
        if (tickers.length === 0) return null;
        const days: Record<string, number> = { '30': 30, '120': 120, '360': 360 };
        const slice = (compareData[tickers[0]] || []).slice(-days[compareRange]);
        if (slice.length === 0) return null;
        const fmt = (d: string) => {
            const [y, m, day] = d.split('-');
            return `${m}/${day}/${y}`;
        };
        return { start: fmt(slice[0].date), end: fmt(slice[slice.length - 1].date) };
    };

    const handleExportCSV = () => {
        const { portfolio_items = [] } = portfolioData || {};
        if (portfolio_items.length === 0) return;
        const headers = [
            'Ticker', 'Quantity', 'Avg Price', 'Current Price',
            'Cost Basis', 'Current Value', 'Gain/Loss $', 'Gain/Loss %',
            '1D Return', '30D Return', '120D Return', '360D Return',
        ];
        const rows = portfolio_items.map((item: PortfolioItemWithMetrics) => [
            item.ticker,
            item.quantity,
            item.avg_price?.toFixed(2) ?? '',
            item.current_price?.toFixed(2) ?? '',
            item.cost_basis?.toFixed(2) ?? '',
            item.current_value?.toFixed(2) ?? '',
            item.total_gain_loss?.toFixed(2) ?? '',
            item.gain_loss_pct != null ? (item.gain_loss_pct * 100).toFixed(2) + '%' : '',
            item.return_1d != null ? (item.return_1d * 100).toFixed(2) + '%' : '',
            item.return_30d != null ? (item.return_30d * 100).toFixed(2) + '%' : '',
            item.return_120d != null ? (item.return_120d * 100).toFixed(2) + '%' : '',
            item.return_360d != null ? (item.return_360d * 100).toFixed(2) + '%' : '',
        ]);
        const csv = [headers, ...rows].map((r) => r.join(',')).join('\n');
        const blob = new Blob([csv], { type: 'text/csv' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = 'portfolio.csv';
        a.click();
        URL.revokeObjectURL(url);
    };

    const handleExportPDF = () => {
        const { portfolio_items = [] } = portfolioData || {};
        const summ = portfolioData?.summary;
        if (portfolio_items.length === 0) return;
        const doc = new jsPDF();
        doc.setFontSize(18);
        doc.text('Portfolio Report', 14, 22);
        doc.setFontSize(10);
        doc.setTextColor(120, 120, 120);
        doc.text(`Generated: ${new Date().toLocaleDateString()}`, 14, 30);
        doc.setTextColor(0, 0, 0);
        const rows = portfolio_items.map((item: PortfolioItemWithMetrics) => [
            item.ticker,
            item.quantity.toString(),
            `$${item.avg_price?.toFixed(2) ?? 'N/A'}`,
            `$${item.current_price?.toFixed(2) ?? 'N/A'}`,
            `$${item.cost_basis?.toFixed(2) ?? 'N/A'}`,
            `$${item.current_value?.toFixed(2) ?? 'N/A'}`,
            `$${item.total_gain_loss?.toFixed(2) ?? 'N/A'}`,
            item.gain_loss_pct != null ? `${(item.gain_loss_pct * 100).toFixed(2)}%` : 'N/A',
        ]);
        autoTable(doc, {
            head: [['Ticker', 'Qty', 'Avg Price', 'Current', 'Cost Basis', 'Value', 'Gain/Loss', 'Return %']],
            body: rows,
            startY: 36,
            styles: { fontSize: 9 },
            headStyles: { fillColor: [99, 102, 241] },
        });
        const finalY = (doc as any).lastAutoTable.finalY + 10;
        doc.setFontSize(12);
        doc.text('Summary', 14, finalY);
        doc.setFontSize(10);
        if (summ) {
            doc.text(`Total Value: ${formatCurrency(summ.total_current_value)}`, 14, finalY + 8);
            doc.text(`Total Invested: ${formatCurrency(summ.total_cost_basis)}`, 14, finalY + 16);
            doc.text(`Total Gain/Loss: ${formatCurrency(summ.total_gain_loss)} (${formatPercent(summ.total_gain_loss_pct)})`, 14, finalY + 24);
            doc.text(`Positions: ${summ.num_positions}`, 14, finalY + 32);
        }
        doc.save('portfolio.pdf');
    };

    // Build merged chart dataset for the comparison LineChart
    const buildChartData = () => {
        const tickers = Object.keys(compareData);
        if (tickers.length === 0) return [];
        const rangeMap: Record<string, number> = { '30': 30, '120': 120, '360': 360 };
        const days = rangeMap[compareRange];
        const baseSlice = (compareData[tickers[0]] || []).slice(-days);

        // first close per ticker for % normalization
        const firstCloses: Record<string, number> = {};
        tickers.forEach((ticker: string) => {
            const slice = (compareData[ticker] || []).slice(-days);
            firstCloses[ticker] = slice[0]?.close || 1;
        });

        return baseSlice.map((point: PricePoint) => {
            const row: Record<string, string | number> = { date: point.date.slice(5) }; // MM-DD
            tickers.forEach((ticker: string) => {
                const slice = (compareData[ticker] || []).slice(-days);
                const match = slice.find((p: PricePoint) => p.date === point.date);
                if (match) {
                    row[ticker] = compareView === 'pct'
                        ? parseFloat(((match.close / firstCloses[ticker] - 1) * 100).toFixed(2))
                        : parseFloat(match.close.toFixed(2));
                }
            });
            return row;
        });
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
                    <LoadingScreen message="Loading portfolio..." />
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
                        <button onClick={fetchPortfolioSummary} className="retry-button">
                            Retry
                        </button>
                    </div>
                </div>
            </div>
        );
    }

    const { portfolio_items = [], summary = {} as PortfolioSummary } = portfolioData || {};
    const comparedItems = portfolio_items.filter(item => selectedTickers.includes(item.ticker));

    // Top performers for trending widget
    const trendingData = [...portfolio_items]
        .filter(item => item.return_1d !== null)
        .sort((a, b) => (b.return_1d ?? -Infinity) - (a.return_1d ?? -Infinity))
        .slice(0, 3)
        .map(item => ({
            ticker: item.ticker,
            return: parseFloat((item.return_1d ?? 0).toFixed(2)),
        }));

    const chartData = buildChartData();

    // Data for per-holding P&L bar chart
    const plChartData = portfolio_items.map(item => ({
        ticker: item.ticker,
        gainLoss: parseFloat((item.total_gain_loss ?? 0).toFixed(2)),
        pct: parseFloat(((item.gain_loss_pct ?? 0) * 100).toFixed(2)),
    }));

    return (
        <div className="app-container">
            <div className="home-background-shapes">
                <div className="home-shape home-shape-1"></div>
                <div className="home-shape home-shape-2"></div>
                <div className="home-shape home-shape-3"></div>
            </div>

            <div className="home-card portfolio-card">
                <div className="home-content">
                    <div className="portfolio-header">
                        <h1>My Portfolio</h1>
                        <p>Track your investments and monitor performances</p>
                    </div>

                    {/* Summary Stats — full width */}
                    <div className="portfolio-summary-grid">
                        <div className="summary-stat-card">
                            <div className="stat-icon">💰</div>
                            <div className="stat-content">
                                <div className="stat-labelP">Total Value</div>
                                <div className="stat-valueP"><AnimatedValue value={summary.total_current_value ?? 0} /></div>
                            </div>
                        </div>
                        <div className="summary-stat-card">
                            <div className="stat-icon">📊</div>
                            <div className="stat-content">
                                <div className="stat-labelP">Total Invested</div>
                                <div className="stat-valueP"><AnimatedValue value={summary.total_cost_basis ?? 0} /></div>
                            </div>
                        </div>
                        <div className={`summary-stat-card ${getReturnColor(summary.total_gain_loss)}`}>
                            <div className="stat-icon">
                                {summary.total_gain_loss >= 0 ? '📈' : '📉'}
                            </div>
                            <div className="stat-content">
                                <div className="stat-labelP">Total Gain/Loss</div>
                                <div className={`stat-valueP ${getReturnColor(summary.total_gain_loss)}`}>
                                    <AnimatedValue value={summary.total_gain_loss ?? 0} />
                                </div>
                                <div className={`stat-subvalue ${getReturnColor(summary.total_gain_loss_pct)}`}>
                                    {formatPercent(summary.total_gain_loss_pct)}
                                </div>
                            </div>
                        </div>
                        <div className="summary-stat-card">
                            <div className="stat-icon">🎯</div>
                            <div className="stat-content">
                                <div className="stat-labelP">Positions</div>
                                <div className="stat-valueP"><AnimatedValue value={summary.num_positions ?? 0} format="integer" /></div>
                            </div>
                        </div>
                    </div>

                    {/* 2-column layout: Holdings (left) | Widgets (right) */}
                    <div className="portfolio-layout">

                        {/* Left: Holdings */}
                        <div className="portfolio-left">
                            <div className="portfolio-holdings-section">
                                <div className="section-header">
                                    <h2 className="section-title">Holdings</h2>
                                    <div className="section-header-actions">
                                        {portfolio_items.length > 0 && (
                                            <>
                                                <button
                                                    className="csv-export-btn"
                                                    onClick={handleExportCSV}
                                                    title="Download portfolio as CSV"
                                                >
                                                    Export CSV
                                                </button>
                                                <button
                                                    className="csv-export-btn"
                                                    onClick={handleExportPDF}
                                                    title="Download portfolio as PDF"
                                                >
                                                    Export PDF
                                                </button>
                                            </>
                                        )}
                                        {portfolio_items.length >= 2 && (
                                            <button
                                                className={`compare-btn ${compareMode ? 'active' : ''}`}
                                                onClick={toggleCompareMode}
                                            >
                                                {compareMode ? 'Done Comparing' : 'Compare'}
                                            </button>
                                        )}
                                    </div>
                                </div>

                                {compareMode && (
                                    <p className="compare-hint">
                                        Select 2 or more holdings to compare them side by side.
                                    </p>
                                )}

                                {portfolio_items.length === 0 ? (
                                    <div className="empty-portfolio">
                                        <p className="empty-message">Your portfolio is empty</p>
                                        <button
                                            onClick={() => navigate('/dashboard')}
                                            className="add-stocks-btn"
                                        >
                                            Add Stocks from Dashboard
                                        </button>
                                    </div>
                                ) : (
                                    <div className="holdings-grid">
                                        {portfolio_items.map((item) => {
                                            const isSelected = selectedTickers.includes(item.ticker);
                                            return (
                                                <div
                                                    key={item.id}
                                                    className={`holding-card ${compareMode && isSelected ? 'compare-selected' : ''}`}
                                                >
                                                    <div className="holding-header">
                                                        <div className="ticker-section">
                                                            {compareMode && (
                                                                <label className="compare-checkbox-wrapper">
                                                                    <input
                                                                        type="checkbox"
                                                                        className="compare-checkbox"
                                                                        checked={isSelected}
                                                                        onChange={() => toggleTickerSelection(item.ticker)}
                                                                    />
                                                                </label>
                                                            )}
                                                            <Link
                                                                to={`/stock/${encodeURIComponent(item.ticker)}`}
                                                                className="ticker-link"
                                                                onClick={(e: React.MouseEvent) => e.stopPropagation()}
                                                            >
                                                                {item.ticker}
                                                            </Link>
                                                            <span className="quantity-badge">{item.quantity} shares</span>
                                                        </div>
                                                        <div className="holding-card-actions">
                                                            <button
                                                                onClick={() => {
                                                                    setAddSharesTicker(item.ticker);
                                                                    setAddSharesPrice(item.current_price ?? item.avg_price);
                                                                }}
                                                                className="add-shares-btn"
                                                                title="Add more shares"
                                                            >
                                                                + Add
                                                            </button>
                                                            <button
                                                                onClick={() => openActionPanel(item.ticker)}
                                                                className="remove-btn"
                                                                title="Manage Position"
                                                            >
                                                                ✕
                                                            </button>
                                                        </div>
                                                    </div>

                                                    <div className="holding-price-section">
                                                        <div className="price-row">
                                                            <span className="price-label">Current Price</span>
                                                            <span className="price-value">{formatCurrency(item.current_price)}</span>
                                                        </div>
                                                        <div className="price-row">
                                                            <span className="price-label">Avg. Price</span>
                                                            <span className="price-value">{formatCurrency(item.avg_price)}</span>
                                                        </div>
                                                    </div>
                                                    <div className="holding-divider"></div>
                                                    <div className="holding-metrics">
                                                        <div className="metric-row">
                                                            <span className="metric-label">Cost Basis</span>
                                                            <span className="metric-value">{formatCurrency(item.cost_basis)}</span>
                                                        </div>
                                                        <div className="metric-row">
                                                            <span className="metric-label">Current Value</span>
                                                            <span className="metric-value">{formatCurrency(item.current_value)}</span>
                                                        </div>
                                                        <div className={`metric-row gain-loss-row ${getReturnColor(item.total_gain_loss)}`}>
                                                            <span className="metric-label">Gain/Loss</span>
                                                            <span className={`metric-value ${getReturnColor(item.total_gain_loss)}`}>
                                                                {getReturnIndicator(item.total_gain_loss)} {formatCurrency(item.total_gain_loss)}
                                                                <span className="gain-loss-pct">
                                                                    ({formatPercent(item.gain_loss_pct)})
                                                                </span>
                                                            </span>
                                                        </div>
                                                    </div>
                                                    <div className="holding-divider"></div>
                                                    <div className="holding-returns">
                                                        <div className="return-item">
                                                            <span className="return-label">1D</span>
                                                            <span className={`return-value ${getReturnColor(item.return_1d)}`}>
                                                                {formatPercent(item.return_1d)}
                                                            </span>
                                                        </div>
                                                        <div className="return-item">
                                                            <span className="return-label">30D</span>
                                                            <span className={`return-value ${getReturnColor(item.return_30d)}`}>
                                                                {formatPercent(item.return_30d)}
                                                            </span>
                                                        </div>
                                                        <div className="return-item">
                                                            <span className="return-label">120D</span>
                                                            <span className={`return-value ${getReturnColor(item.return_120d)}`}>
                                                                {formatPercent(item.return_120d)}
                                                            </span>
                                                        </div>
                                                        <div className="return-item">
                                                            <span className="return-label">360D</span>
                                                            <span className={`return-value ${getReturnColor(item.return_360d)}`}>
                                                                {formatPercent(item.return_360d)}
                                                            </span>
                                                        </div>
                                                    </div>

                                                    {/* Inline action panel */}
                                                    {actionTicker === item.ticker && (
                                                        <div className="action-panel">
                                                            <span className="action-panel-title">Manage {item.ticker}</span>
                                                            {actionError && (
                                                                <div className="action-error">{actionError}</div>
                                                            )}
                                                            <input
                                                                type="number"
                                                                className="action-qty-input"
                                                                min="0.001"
                                                                step="any"
                                                                placeholder={`Shares to sell (max ${item.quantity})`}
                                                                value={sellQty}
                                                                onChange={(e: React.ChangeEvent<HTMLInputElement>) => {
                                                                    setSellQty(e.target.value);
                                                                    setActionError(null);
                                                                }}
                                                            />
                                                            <div className="action-btn-row">
                                                                <button
                                                                    className="action-sell-btn"
                                                                    onClick={() => sellShares(item.ticker, item.quantity)}
                                                                >
                                                                    Sell
                                                                </button>
                                                                <button
                                                                    className="action-remove-all-btn"
                                                                    onClick={() => removeStock(item.ticker)}
                                                                >
                                                                    Remove All
                                                                </button>
                                                                <button
                                                                    className="action-cancel-btn"
                                                                    onClick={closeActionPanel}
                                                                >
                                                                    Cancel
                                                                </button>
                                                            </div>
                                                        </div>
                                                    )}
                                                </div>
                                            );
                                        })}
                                    </div>
                                )}
                            </div>
                        </div>

                        {/* Right: Trending widget + Comparison chart */}
                        <div className="portfolio-right">

                            {/* Per-holding Gain/Loss chart */}
                            {plChartData.length > 0 && (
                                <div className="trending-widget">
                                    <h3 className="widget-title">Gain / Loss by Holding</h3>
                                    <ResponsiveContainer width="100%" height={200}>
                                        <BarChart data={plChartData} margin={{ top: 8, right: 8, left: -16, bottom: 0 }}>
                                            <XAxis dataKey="ticker" tick={{ fontSize: 12, fill: '#94a3b8' }} />
                                            <YAxis tickFormatter={(v: number) => `$${v}`} tick={{ fontSize: 11, fill: '#94a3b8' }} />
                                            <Tooltip
                                                formatter={(v, name) =>
                                                    name === 'gainLoss'
                                                        ? [`$${(v as number).toFixed(2)}`, 'Gain/Loss']
                                                        : [`${(v as number).toFixed(2)}%`, 'Return']
                                                }
                                                contentStyle={{ background: '#1e293b', border: '1px solid rgba(255,255,255,0.1)', borderRadius: 8 }}
                                            />
                                            <Bar dataKey="gainLoss" radius={[4, 4, 0, 0]}>
                                                {plChartData.map((entry, index) => (
                                                    <Cell key={`pl-${index}`} fill={entry.gainLoss >= 0 ? '#10b981' : '#ef4444'} />
                                                ))}
                                            </Bar>
                                        </BarChart>
                                    </ResponsiveContainer>
                                </div>
                            )}

                            {/* Trending widget */}
                            {trendingData.length > 0 && (
                                <div className="trending-widget">
                                    <h3 className="widget-title">Top Performers Today</h3>
                                    <ResponsiveContainer width="100%" height={200}>
                                        <BarChart data={trendingData} margin={{ top: 8, right: 8, left: -16, bottom: 0 }}>
                                            <XAxis dataKey="ticker" tick={{ fontSize: 12, fill: '#94a3b8' }} />
                                            <YAxis tickFormatter={(v: number) => `${v}%`} tick={{ fontSize: 11, fill: '#94a3b8' }} />
                                            <Tooltip formatter={(v) => [`${v as number}%`, '1D Return']} />
                                            <Bar dataKey="return" radius={[4, 4, 0, 0]}>
                                                {trendingData.map((entry, index) => (
                                                    <Cell key={`cell-${index}`} fill={entry.return >= 0 ? '#10b981' : '#ef4444'} />
                                                ))}
                                            </Bar>
                                        </BarChart>
                                    </ResponsiveContainer>
                                </div>
                            )}

                            {/* Comparison chart */}
                            {compareMode && selectedTickers.length >= 2 && (
                                <div className="comparison-chart-section">
                                    <h3 className="widget-title">Price Comparison</h3>
                                    {!compareLoading && (() => {
                                        const range = getChartDateRange();
                                        return range ? (
                                            <div className="chart-date-range">
                                                {compareView === 'pct' ? '% Return normalized' : 'Price'} for {range.start} – {range.end}
                                            </div>
                                        ) : null;
                                    })()}
                                    <div className="compare-controls">
                                        <div className="compare-view-toggle">
                                            <button
                                                className={compareView === 'pct' ? 'active' : ''}
                                                onClick={() => setCompareView('pct')}
                                            >
                                                % Return
                                            </button>
                                            <button
                                                className={compareView === 'price' ? 'active' : ''}
                                                onClick={() => setCompareView('price')}
                                            >
                                                Price
                                            </button>
                                        </div>
                                        <div className="compare-range-btns">
                                            {(['30', '120', '360'] as const).map(r => (
                                                <button
                                                    key={r}
                                                    className={compareRange === r ? 'active' : ''}
                                                    onClick={() => setCompareRange(r)}
                                                >
                                                    {r}D
                                                </button>
                                            ))}
                                        </div>
                                    </div>
                                    {compareLoading ? (
                                        <div className="chart-loading">Loading chart...</div>
                                    ) : chartData.length > 0 ? (
                                        <ResponsiveContainer width="100%" height={260}>
                                            <AreaChart data={chartData} margin={{ top: 8, right: 8, left: -16, bottom: 0 }}>
                                                <defs>
                                                    {selectedTickers.map((ticker, i) => (
                                                        <linearGradient key={ticker} id={`grad-${ticker}`} x1="0" y1="0" x2="0" y2="1">
                                                            <stop offset="5%" stopColor={CHART_COLORS[i % CHART_COLORS.length]} stopOpacity={0.25} />
                                                            <stop offset="95%" stopColor={CHART_COLORS[i % CHART_COLORS.length]} stopOpacity={0} />
                                                        </linearGradient>
                                                    ))}
                                                </defs>
                                                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.07)" />
                                                <XAxis
                                                    dataKey="date"
                                                    tick={{ fontSize: 10, fill: '#94a3b8' }}
                                                    interval={Math.floor(chartData.length / 5)}
                                                />
                                                <YAxis
                                                    tick={{ fontSize: 10, fill: '#94a3b8' }}
                                                    tickFormatter={(v: number) => compareView === 'pct' ? `${v}%` : `$${v}`}
                                                />
                                                <Tooltip
                                                    formatter={(v, name) =>
                                                        compareView === 'pct' ? [`${(v as number).toFixed(2)}%`, name] : [`$${(v as number).toFixed(2)}`, name]
                                                    }
                                                    contentStyle={{ background: '#1e293b', border: '1px solid rgba(255,255,255,0.1)', borderRadius: 8 }}
                                                    labelStyle={{ color: '#94a3b8', fontSize: 11 }}
                                                />
                                                <Legend />
                                                {selectedTickers.map((ticker, i) => (
                                                    <Area
                                                        key={ticker}
                                                        type="monotone"
                                                        dataKey={ticker}
                                                        stroke={CHART_COLORS[i % CHART_COLORS.length]}
                                                        fill={`url(#grad-${ticker})`}
                                                        dot={false}
                                                        strokeWidth={2}
                                                    />
                                                ))}
                                            </AreaChart>
                                        </ResponsiveContainer>
                                    ) : (
                                        <div className="chart-loading">No data available</div>
                                    )}
                                </div>
                            )}
                        </div>
                    </div>

                    {/* Comparison table full width, below 2-col */}
                    {compareMode && comparedItems.length >= 2 && (
                        <div className="comparison-section">
                            <h3 className="comparison-title">Side-by-Side Comparison</h3>
                            <div className="comparison-table-wrapper">
                                <table className="comparison-table">
                                    <thead>
                                        <tr>
                                            <th>Metric</th>
                                            {comparedItems.map(item => (
                                                <th key={item.ticker}>{item.ticker}</th>
                                            ))}
                                        </tr>
                                    </thead>
                                    <tbody>
                                        <tr>
                                            <td>Current Price</td>
                                            {comparedItems.map(item => (
                                                <td key={item.ticker}>{formatCurrency(item.current_price)}</td>
                                            ))}
                                        </tr>
                                        <tr>
                                            <td>Avg. Price</td>
                                            {comparedItems.map(item => (
                                                <td key={item.ticker}>{formatCurrency(item.avg_price)}</td>
                                            ))}
                                        </tr>
                                        <tr>
                                            <td>Quantity</td>
                                            {comparedItems.map(item => (
                                                <td key={item.ticker}>{item.quantity}</td>
                                            ))}
                                        </tr>
                                        <tr>
                                            <td>Cost Basis</td>
                                            {comparedItems.map(item => (
                                                <td key={item.ticker}>{formatCurrency(item.cost_basis)}</td>
                                            ))}
                                        </tr>
                                        <tr>
                                            <td>Current Value</td>
                                            {comparedItems.map(item => (
                                                <td key={item.ticker}>{formatCurrency(item.current_value)}</td>
                                            ))}
                                        </tr>
                                        <tr>
                                            <td>Gain / Loss</td>
                                            {comparedItems.map(item => (
                                                <td key={item.ticker} className={getReturnColor(item.total_gain_loss)}>
                                                    {formatCurrency(item.total_gain_loss)}
                                                    <span style={{ fontSize: '0.8rem', marginLeft: '0.25rem' }}>
                                                        ({formatPercent(item.gain_loss_pct)})
                                                    </span>
                                                </td>
                                            ))}
                                        </tr>
                                        <tr>
                                            <td>1D Return</td>
                                            {comparedItems.map(item => (
                                                <td key={item.ticker} className={getReturnColor(item.return_1d)}>
                                                    {formatPercent(item.return_1d)}
                                                </td>
                                            ))}
                                        </tr>
                                        <tr>
                                            <td>30D Return</td>
                                            {comparedItems.map(item => (
                                                <td key={item.ticker} className={getReturnColor(item.return_30d)}>
                                                    {formatPercent(item.return_30d)}
                                                </td>
                                            ))}
                                        </tr>
                                        <tr>
                                            <td>120D Return</td>
                                            {comparedItems.map(item => (
                                                <td key={item.ticker} className={getReturnColor(item.return_120d)}>
                                                    {formatPercent(item.return_120d)}
                                                </td>
                                            ))}
                                        </tr>
                                        <tr>
                                            <td>360D Return</td>
                                            {comparedItems.map(item => (
                                                <td key={item.ticker} className={getReturnColor(item.return_360d)}>
                                                    {formatPercent(item.return_360d)}
                                                </td>
                                            ))}
                                        </tr>
                                    </tbody>
                                </table>
                            </div>
                        </div>
                    )}
                </div>
            </div>
        {addSharesTicker && (
            <AddToPortfolioModal
                ticker={addSharesTicker}
                currentPrice={addSharesPrice}
                onClose={() => setAddSharesTicker(null)}
                onSuccess={() => {
                    setAddSharesTicker(null);
                    fetchPortfolioSummary();
                }}
            />
        )}
    </div>
);
};
export default Portfolio;
