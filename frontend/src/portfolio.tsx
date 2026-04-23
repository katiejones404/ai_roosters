/*
 * Portfolio.tsx
 * Portfolio management page where users track stock positions, view gain and
 * loss metrics, compare historical price performance, and export data as CSV or PDF.
 */
import React, { useState, useEffect } from "react";
import axios from "axios";
import { useNavigate, Link } from "react-router-dom";
import { getToken } from "./utils/auth";
import {
    BarChart, Bar, XAxis, YAxis, Tooltip,
    ResponsiveContainer, Cell,
} from "recharts";
import AddToPortfolioModal from "./components/AddToPortfolio";
import ImportPortfolioModal from "./components/ImportPortfolioModal";
import LoadingScreen from "./components/LoadingScreen";
import jsPDF from 'jspdf';
import autoTable from 'jspdf-autotable';
import './portfolio.css';

const API_BASE = (import.meta.env.VITE_API_BASE_URL || "http://localhost:8000").replace(/\/+$/, "");

interface Transaction {
    id: string;
    ticker: string;
    action: 'buy' | 'sell';
    quantity: number;
    price: number;
    realized_gain: number | null;
    executed_at: string;
}

interface RealizedSummary {
    ticker: string;
    total_realized: number;
    num_sells: number;
}

interface PortfolioItemWithMetrics {
    id: string;
    ticker: string;
    quantity: number;
    avg_price: number;
    current_price: number | null;
    cost_basis: number;
    current_value: number;
    total_gain_loss: number;
    gain_loss_pct: number;   // decimal from backend, e.g. 0.15 = +15%
    return_1d: number | null;
    return_30d: number | null;
    return_120d: number | null;
    return_360d: number | null;
    added_at: string | null;
}

interface PortfolioSummary {
    total_cost_basis: number;
    total_current_value: number;
    total_gain_loss: number;       // unrealized $
    total_gain_loss_pct: number;   // unrealized % as decimal
    total_realized_gain: number;   // locked-in $ from all sells
    num_positions: number;
}

interface PortfolioData {
    portfolio_items: PortfolioItemWithMetrics[];
    summary: PortfolioSummary;
}



/*
AnimatedValue

Counts up from 0 to the target value on mount using requestAnimationFrame.
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
    const [actionTicker, setActionTicker] = useState<string | null>(null);
    const [sellQty, setSellQty] = useState<string>('');
    const [actionError, setActionError] = useState<string | null>(null);
    const [addSharesTicker, setAddSharesTicker] = useState<string | null>(null);
    const [addSharesPrice, setAddSharesPrice] = useState<number>(0);
    const [showImport, setShowImport] = useState(false);
    const [transactions, setTransactions] = useState<Transaction[]>([]);
    const [, setRealizedSummary] = useState<RealizedSummary[]>([]);
    const [showTransactions, setShowTransactions] = useState(false);

    useEffect(() => {
        fetchPortfolioSummary();
        fetchTransactions();
    }, []);

    const fetchTransactions = async () => {
        try {
            const token = getToken();
            const [txRes, summaryRes] = await Promise.all([
                axios.get(`${API_BASE}/api/portfolio/transactions`, {
                    headers: { Authorization: `Bearer ${token}` }
                }),
                axios.get(`${API_BASE}/api/portfolio/transactions/summary`, {
                    headers: { Authorization: `Bearer ${token}` }
                })
            ]);
            setTransactions(txRes.data);
            setRealizedSummary(summaryRes.data);
        } catch {
            // non-fatal — portfolio still works without transaction history
        }
    };

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
                        total_gain_loss_pct: 0,
                        total_realized_gain: 0,
                        num_positions: 0,
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
            closeActionPanel();
            fetchPortfolioSummary();
            fetchTransactions();
        } catch {
            setActionError('Failed to remove position. Please try again.');
        }
    };

    const sellShares = async (ticker: string, currentQty: number) => {
        const qty = parseFloat(sellQty);
        if (isNaN(qty) || qty < 0.0001) {
            setActionError('Enter a number of shares to sell of at least 0.0001.');
            return;
        }
        try {
            const token = getToken();
            if (qty >= currentQty) {
                await axios.delete(`${API_BASE}/api/portfolio/${ticker}`, {
                    headers: { Authorization: `Bearer ${token}` }
                });
            } else {
                await axios.put(
                    `${API_BASE}/api/portfolio/${ticker}`,
                    { quantity: parseFloat((currentQty - qty).toFixed(6)) },
                    { headers: { Authorization: `Bearer ${token}` } }
                );
            }
            closeActionPanel();
            fetchPortfolioSummary();
            fetchTransactions();
        } catch {
            setActionError('Failed to update position. Please try again.');
        }
    };

    const formatCurrency = (value: number | null) => {
        if (value === null || value === undefined) return 'N/A';
        return new Intl.NumberFormat('en-US', {
            style: 'currency', currency: 'USD',
            minimumFractionDigits: 2, maximumFractionDigits: 2,
        }).format(value);
    };

    const formatPercent = (value: number | null) => {
        if (value === null || value === undefined) return 'N/A';
        const pct = value * 100;
        const sign = pct >= 0 ? '+' : '';
        return `${sign}${pct.toFixed(2)}%`;
    };

    const getReturnColor = (value: number | null): string => {
        if (value === null || value === undefined) return '';
        return value >= 0 ? 'positive' : 'negative';
    };

    const getReturnIndicator = (value: number | null): string => {
        if (value === null || value === undefined) return '-';
        return value >= 0 ? '▲' : '▼';
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
            formatCurrency(item.avg_price ?? null),
            formatCurrency(item.current_price ?? null),
            formatCurrency(item.cost_basis ?? null),
            formatCurrency(item.current_value ?? null),
            formatCurrency(item.total_gain_loss ?? null),
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
            doc.text(`Unrealized Gain/Loss: ${formatCurrency(summ.total_gain_loss)} (${formatPercent(summ.total_gain_loss_pct)})`, 14, finalY + 24);
            doc.text(`Realized Gain: ${formatCurrency(summ.total_realized_gain)}`, 14, finalY + 32);
            doc.text(`Positions: ${summ.num_positions}`, 14, finalY + 40);
        }
        doc.save('portfolio.pdf');
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
                        <button onClick={fetchPortfolioSummary} className="retry-button">Retry</button>
                    </div>
                </div>
            </div>
        );
    }

    const { portfolio_items = [], summary = {} as PortfolioSummary } = portfolioData || {};

    const trendingData = [...portfolio_items]
        .filter(item => item.return_1d !== null)
        .sort((a, b) => (b.return_1d ?? -Infinity) - (a.return_1d ?? -Infinity))
        .slice(0, 3)
        .map(item => ({
            ticker: item.ticker,
            return: parseFloat(((item.return_1d ?? 0) * 100).toFixed(2)),
        }));

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

                        <div className={`summary-stat-card ${(summary.total_realized_gain ?? 0) >= 0 ? 'positive' : 'negative'}`}>
                            <div className="stat-icon">🔒</div>
                            <div className="stat-content">
                                <div className="stat-labelP">Realized Gain</div>
                                <div className={`stat-valueP ${(summary.total_realized_gain ?? 0) >= 0 ? 'positive' : 'negative'}`}>
                                    <AnimatedValue value={summary.total_realized_gain ?? 0} />
                                </div>
                                <div className="stat-subvalue" style={{ color: 'rgba(255,255,255,0.4)', fontSize: '0.75rem' }}>
                                    Locked in from sells
                                </div>
                            </div>
                        </div>

                        <div className={`summary-stat-card ${getReturnColor(summary.total_gain_loss)}`}>
                            <div className="stat-icon">{(summary.total_gain_loss ?? 0) >= 0 ? '📈' : '📉'}</div>
                            <div className="stat-content">
                                <div className="stat-labelP">Unrealized Gain/Loss</div>
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

                    <div className="portfolio-layout">
                        <div className="portfolio-left">
                            <div className="portfolio-holdings-section">
                                <div className="section-header">
                                    <h2 className="section-title">Holdings</h2>
                                    <div className="section-header-actions">
                                        <button
                                            className="csv-export-btn"
                                            onClick={() => setShowImport(true)}
                                            title="Add stock by purchase date"
                                        >
                                            + Add By Date
                                        </button>
                                        {portfolio_items.length > 0 && (
                                            <>
                                                <button className="csv-export-btn" onClick={handleExportCSV} title="Download portfolio as CSV">
                                                    Export CSV
                                                </button>
                                                <button className="csv-export-btn" onClick={handleExportPDF} title="Download portfolio as PDF">
                                                    Export PDF
                                                </button>
                                            </>
                                        )}
                                    </div>
                                </div>

                                {portfolio_items.length === 0 ? (
                                    <div className="empty-portfolio">
                                        <p className="empty-message">Your portfolio is empty</p>
                                        <div className="onboard-options">
                                            <button className="add-stocks-btn" onClick={() => setShowImport(true)}>
                                                Import Existing Holdings
                                            </button>
                                            <button className="add-stocks-btn" onClick={() => navigate('/dashboard')}>
                                                Browse the Dashboard
                                            </button>
                                        </div>
                                    </div>
                                ) : (
                                    <div className="holdings-grid">
                                        {portfolio_items.map((item) => (
                                            <div key={item.id} className="holding-card">
                                                <div className="holding-header">
                                                    <div className="ticker-section">
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
                                                        <span className="metric-label">Unrealized Gain/Loss</span>
                                                        <span className={`metric-value ${getReturnColor(item.total_gain_loss)}`}>
                                                            {getReturnIndicator(item.total_gain_loss)} {formatCurrency(item.total_gain_loss)}
                                                            <span className="gain-loss-pct">({formatPercent(item.gain_loss_pct)})</span>
                                                        </span>
                                                    </div>
                                                </div>

                                                <div className="holding-divider"></div>

                                                <div className="holding-returns">
                                                    <div className="return-item">
                                                        <span className="return-label">1D</span>
                                                        <span className={`return-value ${getReturnColor(item.return_1d)}`}>{formatPercent(item.return_1d)}</span>
                                                    </div>
                                                    <div className="return-item">
                                                        <span className="return-label">30D</span>
                                                        <span className={`return-value ${getReturnColor(item.return_30d)}`}>{formatPercent(item.return_30d)}</span>
                                                    </div>
                                                    <div className="return-item">
                                                        <span className="return-label">120D</span>
                                                        <span className={`return-value ${getReturnColor(item.return_120d)}`}>{formatPercent(item.return_120d)}</span>
                                                    </div>
                                                    <div className="return-item">
                                                        <span className="return-label">360D</span>
                                                        <span className={`return-value ${getReturnColor(item.return_360d)}`}>{formatPercent(item.return_360d)}</span>
                                                    </div>
                                                </div>

                                                {actionTicker === item.ticker && (
                                                    <div className="action-panel">
                                                        <span className="metric-label">Manage {item.ticker}</span>
                                                        {actionError && <div className="action-error">{actionError}</div>}
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
                                                            <button className="action-sell-btn" onClick={() => sellShares(item.ticker, item.quantity)}>
                                                                Sell
                                                            </button>
                                                            <button className="action-remove-all-btn" onClick={() => removeStock(item.ticker)}>
                                                                Remove All
                                                            </button>
                                                            <button className="action-cancel-btn" onClick={closeActionPanel}>
                                                                Cancel
                                                            </button>
                                                        </div>
                                                    </div>
                                                )}
                                            </div>
                                        ))}
                                    </div>
                                )}
                            </div>
                        </div>

                        <div className="portfolio-right">
                            {plChartData.length > 0 && (
                                <div className="trending-widget">
                                    <h3 className="widget-title">Gain / Loss by Holding</h3>
                                    <ResponsiveContainer width="100%" height={200}>
                                        <BarChart data={plChartData} margin={{ top: 8, right: 8, left: -16, bottom: 0 }}>
                                            <XAxis dataKey="ticker" tick={{ fontSize: 12, fill: '#94a3b8' }} />
                                            <YAxis tickFormatter={(v: number) => `$${v}`} tick={{ fontSize: 11, fill: '#94a3b8' }} />
                                            <Tooltip
                                                cursor={{ fill: 'rgba(255, 255, 255, 0.24)' }}
                                                formatter={(v, name) =>
                                                    name === 'gainLoss'
                                                        ? [`$${(v as number).toFixed(2)}`, 'Gain/Loss']
                                                        : [`${(v as number).toFixed(2)}%`, 'Return']
                                                }
                                                contentStyle={{ background:'#1e293b', border: '1px solid rgba(255,255,255,0.1)', borderRadius: 8 }}
                                                itemStyle={{ color: '#eaeaea' }}
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
                        </div>
                    </div>

                    {transactions.length > 0 && (
                        <div className="comparison-section">
                            <div className="section-header">
                                <h3 className="comparison-title">Transaction History</h3>
                                <button className="csv-export-btn" onClick={() => setShowTransactions(prev => !prev)}>
                                    {showTransactions ? 'Hide' : 'Show'}
                                </button>
                            </div>
                            {showTransactions && (
                                <div className="comparison-table-wrapper">
                                    <table className="comparison-table">
                                        <thead>
                                            <tr>
                                                <th>Date</th>
                                                <th>Ticker</th>
                                                <th>Action</th>
                                                <th>Shares</th>
                                                <th>Price</th>
                                                <th>Total</th>
                                                <th>Realized Gain</th>
                                            </tr>
                                        </thead>
                                        <tbody>
                                            {transactions.map((tx) => (
                                                <tr key={tx.id}>
                                                    <td>{new Date(tx.executed_at).toLocaleDateString()}</td>
                                                    <td>{tx.ticker}</td>
                                                    <td style={{
                                                        color: tx.action === 'buy' ? '#10b981' : '#f59e0b',
                                                        fontWeight: 700,
                                                        textTransform: 'uppercase',
                                                    }}>
                                                        {tx.action}
                                                    </td>
                                                    <td>{tx.quantity}</td>
                                                    <td>{formatCurrency(tx.price)}</td>
                                                    <td>{formatCurrency(tx.quantity * tx.price)}</td>
                                                    <td className={
                                                        tx.realized_gain === null ? '' :
                                                        tx.realized_gain >= 0 ? 'positive' : 'negative'
                                                    }>
                                                        {tx.realized_gain === null ? '—' : formatCurrency(tx.realized_gain)}
                                                    </td>
                                                </tr>
                                            ))}
                                        </tbody>
                                    </table>
                                </div>
                            )}
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
                        fetchTransactions();
                    }}
                />
            )}
            {showImport && (
                <ImportPortfolioModal
                    onClose={() => setShowImport(false)}
                    onSuccess={() => {
                        setShowImport(false);
                        fetchPortfolioSummary();
                        fetchTransactions();
                    }}
                />
            )}
        </div>
    );
};

export default Portfolio;
