import axios from "axios";
import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { getToken } from "./utils/auth";
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

const Portfolio = () => {
    const navigate = useNavigate();
    const [portfolioData, setPortfolioData] = useState<PortfolioData | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        fetchPortfolioSummary();
    }, []);

    const fetchPortfolioSummary = async () => {
        try {
            setLoading(true);
            const token = getToken();
        
            if (!token) {
                navigate('/dashboard');
                return;
            }

            const  response = await axios.get(`${API_BASE}/api/portfolio/stats/summary`, {
                headers: {
                    Authorization: `Bearer ${token}`
                }
            });
            setPortfolioData(response.data);
            setError(null);
        } catch (err: any) {
            console.error('Error fetching portfolio:', err);
            if (err.response?.status === 404) {
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
            } else if (err.response?.status === 401) {
                navigate('/dashboard');
            } else {
                setError('Failed to load portfolio data');
            }
        } finally {
            setLoading(false);
        }
    };

    const removeStock = async (ticker: string) => {
        if (!confirm(`Remove ${ticker} from portfolio?`)) return;

        try {
            // Use axios - token added automatically
            const token = getToken();
            await axios.delete(`${API_BASE}/api/portfolio/${ticker}`, {
                headers: {
                    Authorization: `Bearer ${token}`
                }
            });
            fetchPortfolioSummary();
        } catch (err) {
            console.error('Error removing stock:', err);
            alert('Failed to remove stock from portfolio');
        }
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

    const  getReturnIndicator = (value: number | null): string => {
        if (value === null || value === undefined) return '-';
        return value >= 0 ? '▲' : '▼';
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
                    <div className="portfolio-loading">
                        <div className="loading-spinner"></div>
                        <p>Loading portfolio...</p>
                    </div>
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

    return (
        <div className="app-container">
            <div className="home-background-shapes">
                <div className="home-shape home-shape-1"></div>
                <div className="home-shape home-shape-2"></div>
                <div className="home-shape home-shape-3"></div>
            </div>

            <div className="home-card">
                <div className="home-content">
                    <div className="portfolio-header">
                        <h1>My Portfolio</h1>
                        <p>Track your investments and monitor performances</p>
                    </div>

                    {/* Summary Stats */}
                    <div className="portfolio-summary-grid">
                        <div className="summary-stat-card">
                            <div className="stat-icon">💰</div>
                            <div className="stat-content">
                                <div className="stat-labelP">Total Value</div>
                                <div className="stat-valueP">{formatCurrency(summary.total_current_value)}</div>
                            </div>
                        </div>
                        <div className="summary-stat-card">
                            <div className="stat-icon">📊</div>
                            <div className="stat-content">
                                <div className="stat-labelP">Total Invested</div>
                                <div className="stat-valueP">{formatCurrency(summary.total_cost_basis)}</div>
                            </div>
                        </div>
                        <div className={`summary-stat-card ${getReturnColor(summary.total_gain_loss)}`}>
                            <div className="stat-icon">
                                {summary.total_gain_loss >= 0 ? '📈' : '📉'}
                            </div>
                            <div className="stat-content">
                                <div className="stat-labelP">Total Gain/Loss</div>
                                <div className={`stat-valueP ${getReturnColor(summary.total_gain_loss)}`}>
                                    {formatCurrency(summary.total_gain_loss)}
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
                                <div className="stat-valueP">{summary.num_positions || 0}</div>
                            </div>
                        </div>
                    </div>

                    {/* Holdings Section */}
                    <div className="portfolio-holdings-section">
                        <h2 className="section-title">Holdings</h2>

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
                                {portfolio_items.map((item) => (
                                    <div key={item.id} className="holding-card">
                                        <div className="holding-header">
                                            <div className="ticker-section">
                                                <span className="ticker-symbol">{item.ticker}</span>
                                                <span className="quantity-badge">{item.quantity} shares</span>
                                            </div>
                                            <button 
                                                onClick={() => removeStock(item.ticker)}
                                                className="remove-btn"
                                                title="Remove from Portfolio"
                                            >
                                                ✕
                                            </button>
                                        </div>

                                        <div className="holding-price-section">
                                            <div className="price-row">
                                                <span className="price-label">Current Price</span>
                                                <span className="price-value">
                                                    {formatCurrency(item.current_price)}
                                                </span>
                                            </div>
                                            <div className="price-row">
                                                <span className="price-label">Avg. Price</span>
                                                <span className="price-value">
                                                    {formatCurrency(item.avg_price)}
                                                </span>
                                            </div>
                                        </div>
                                        <div className="holding-divider"></div>
                                        <div className="holding-metrics">
                                            <div className="metric-row">
                                                <span className="metric-label">Cost Basis</span>
                                                <span className="metric-value">
                                                    {formatCurrency(item.cost_basis)}
                                                </span>
                                            </div>
                                            <div className="metric-row">
                                                <span className="metric-label">Current Value</span>
                                                <span className="metric-value">
                                                    {formatCurrency(item.current_value)}
                                                </span>
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
                                    </div>
                                ))}
                            </div>
                        )}
                    </div>
                </div>
            </div>
        </div>
    );
};

export default Portfolio;