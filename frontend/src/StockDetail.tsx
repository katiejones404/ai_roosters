import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import axios from 'axios';
import AddToPortfolioModal from './components/AddToPortfolio';
import {
  LineChart, Line, XAxis, YAxis, Tooltip,
  ResponsiveContainer, CartesianGrid
} from 'recharts';

const API_BASE = (import.meta.env.VITE_API_BASE_URL || "http://localhost:8000").replace(/\/+$/, "");

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
  if (value == null) return 'N/A';
  return new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(value);
};

const formatPercent = (value: number | null | undefined): string => {
  if (value == null) return 'N/A';
  return `${value >= 0 ? '+' : ''}${(value * 100).toFixed(2)}%`;
};

const getReturnColor = (value: number | null | undefined): string => {
  if (value == null) return '#6b7280';
  return value >= 0 ? '#16a34a' : '#dc2626';
};

const calcReturn = (from: number | null, to: number | null): number | null => {
  if (!from || !to) return null;
  return (to - from) / from;
};

const CustomTooltip = ({ active, payload, label }: any) => {
  if (!active || !payload?.length) return null;
  return (
    <div style={{
      background: '#fff', border: '1px solid #e2e8f0', borderRadius: 10,
      padding: '10px 14px', boxShadow: '0 4px 20px rgba(0,0,0,0.08)'
    }}>
      <p style={{ margin: 0, fontSize: 12, color: '#94a3b8' }}>
        {new Date(label).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })}
      </p>
      <p style={{ margin: '4px 0 0', fontSize: 16, fontWeight: 700, color: '#0f172a' }}>
        {formatCurrency(payload[0].value)}
      </p>
    </div>
  );
};

const StockDetail: React.FC = () => {
  const { ticker } = useParams<{ ticker: string }>();
  const navigate = useNavigate();

  const [allData, setAllData] = useState<PriceData[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [timeRange, setTimeRange] = useState<'7' | '30' | '120' | '360'>('30');
  const [showModal, setShowModal] = useState(false);

  useEffect(() => {
    if (!ticker) return;
    setLoading(true);
    axios.get<PriceData[]>(`${API_BASE}/api/stocks/${ticker}/prices`)
      .then(res => { setAllData(res.data); setError(null); })
      .catch(() => setError('Failed to load stock data'))
      .finally(() => setLoading(false));
  }, [ticker]);

  const latest = allData.length ? allData[allData.length - 1] : null;
  const oldest = allData.length ? allData[0] : null;

  // Date range relative to LAST available data point, not today
  const chartData = (() => {
    if (!allData.length || !latest) return [];
    const days = parseInt(timeRange);
    const lastDate = new Date(latest.date);
    const cutoff = new Date(lastDate);
    cutoff.setDate(cutoff.getDate() - days);
    return allData
      .filter(d => d.close != null && new Date(d.date) >= cutoff)
      .map(d => ({ date: d.date, close: d.close }));
  })();

  // Calculate returns from price data since DB columns are null
  const getPriceNDaysAgo = (days: number): number | null => {
    if (!latest) return null;
    const lastDate = new Date(latest.date);
    const targetDate = new Date(lastDate);
    targetDate.setDate(targetDate.getDate() - days);
    const candidates = allData.filter(d => d.close != null && new Date(d.date) <= targetDate);
    if (!candidates.length) return null;
    return candidates[candidates.length - 1].close;
  };

  const ret1d   = calcReturn(getPriceNDaysAgo(1),   latest?.close ?? null);
  const ret30d  = calcReturn(getPriceNDaysAgo(30),  latest?.close ?? null);
  const ret120d = calcReturn(getPriceNDaysAgo(120), latest?.close ?? null);
  const ret360d = calcReturn(getPriceNDaysAgo(360), latest?.close ?? null);

  const rangeFirst  = chartData[0]?.close ?? null;
  const rangeLast   = chartData[chartData.length - 1]?.close ?? null;
  const rangeChange = calcReturn(rangeFirst, rangeLast);
  const isPositive  = (rangeChange ?? 0) >= 0;
  const accentColor = isPositive ? '#16a34a' : '#dc2626';

  const addToPortfolio = () => {
    setShowModal(true);
  };

  if (loading) return (
    <div style={{ minHeight: '100vh', background: '#f8fafc', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
      <div style={{ textAlign: 'center' }}>
        <div style={{
          width: 44, height: 44, borderRadius: '50%',
          border: '3px solid #e2e8f0', borderTopColor: '#6366f1',
          animation: 'spin 0.8s linear infinite', margin: '0 auto'
        }} />
        <p style={{ color: '#94a3b8', marginTop: 16 }}>Loading {ticker}...</p>
      </div>
      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
    </div>
  );

  if (error) return (
    <div style={{ minHeight: '100vh', background: '#f8fafc', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
      <div style={{ textAlign: 'center' }}>
        <p style={{ color: '#ef4444', fontSize: 18 }}>{error}</p>
        <button onClick={() => navigate('/dashboard')} style={{
          marginTop: 16, padding: '10px 24px', background: '#6366f1',
          color: '#fff', border: 'none', borderRadius: 10, cursor: 'pointer', fontWeight: 600
        }}>← Back to Dashboard</button>
      </div>
    </div>
  );

  return (
    <div style={{ minHeight: '100vh', background: '#f8fafc', fontFamily: 'system-ui, sans-serif', color: '#0f172a' }}>
      <style>{`
        @keyframes spin  { to { transform: rotate(360deg); } }
        @keyframes fadeUp { from { opacity:0; transform:translateY(10px); } to { opacity:1; transform:translateY(0); } }
        .stat-card { animation: fadeUp 0.3s ease both; }
        .stat-card:nth-child(1) { animation-delay: 0.05s; }
        .stat-card:nth-child(2) { animation-delay: 0.10s; }
        .stat-card:nth-child(3) { animation-delay: 0.15s; }
        .stat-card:nth-child(4) { animation-delay: 0.20s; }
        .range-btn { border: none; border-radius: 8px; padding: 6px 14px; font-size: 13px; font-weight: 600; cursor: pointer; transition: all 0.15s ease; }
        .perf-row { display: flex; justify-content: space-between; align-items: center; padding: 12px 0; border-bottom: 1px solid #f1f5f9; }
        .perf-row:last-child { border-bottom: none; }
      `}</style>

      {/* Header */}
      <div style={{ background: '#fff', borderBottom: '1px solid #e2e8f0', padding: '16px 32px', display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 12 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
          <button onClick={() => navigate(-1)} style={{
            background: '#f8fafc', border: '1px solid #e2e8f0', color: '#64748b',
            borderRadius: 8, padding: '8px 14px', cursor: 'pointer', fontSize: 14, fontWeight: 500
          }}>← Back</button>
          <div>
            <div style={{ display: 'flex', alignItems: 'baseline', gap: 12, flexWrap: 'wrap' }}>
              <h1 style={{ margin: 0, fontSize: 28, fontWeight: 800, letterSpacing: '-0.02em' }}>{ticker}</h1>
              {latest?.close != null && (
                <span style={{ fontSize: 22, fontWeight: 600, color: '#475569' }}>
                  {formatCurrency(latest.close)}
                </span>
              )}
              {rangeChange != null && (
                <span style={{
                  fontSize: 13, fontWeight: 600, color: accentColor,
                  background: isPositive ? '#dcfce7' : '#fee2e2',
                  padding: '3px 10px', borderRadius: 20,
                }}>
                  {formatPercent(rangeChange)} ({timeRange}D)
                </span>
              )}
            </div>
            {oldest && latest && (
              <p style={{ margin: '2px 0 0', fontSize: 12, color: '#94a3b8' }}>
                Data from {new Date(oldest.date).toLocaleDateString()} – {new Date(latest.date).toLocaleDateString()}
              </p>
            )}
          </div>
        </div>
        <button onClick={addToPortfolio} style={{
          background: 'linear-gradient(135deg, #6366f1, #8b5cf6)',
          color: '#fff', border: 'none', borderRadius: 10,
          padding: '10px 22px', fontWeight: 600, fontSize: 14, cursor: 'pointer'
        }}>+ Add to Portfolio</button>
      </div>

      <div style={{ maxWidth: 1100, margin: '0 auto', padding: '32px 24px' }}>

        {/* Stat cards */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))', gap: 16, marginBottom: 28 }}>
          {[
            { label: 'Current Price', value: formatCurrency(latest?.close), color: '#0f172a' },
            { label: '1-Day Return',   value: formatPercent(ret1d),   color: getReturnColor(ret1d)   },
            { label: '30-Day Return',  value: formatPercent(ret30d),  color: getReturnColor(ret30d)  },
            { label: '1-Year Return',  value: formatPercent(ret360d), color: getReturnColor(ret360d) },
          ].map(({ label, value, color }) => (
            <div key={label} className="stat-card" style={{
              background: '#fff', border: '1px solid #e2e8f0',
              borderRadius: 14, padding: '20px 22px'
            }}>
              <p style={{ margin: 0, fontSize: 11, color: '#94a3b8', textTransform: 'uppercase', letterSpacing: '0.08em' }}>{label}</p>
              <p style={{ margin: '8px 0 0', fontSize: 22, fontWeight: 700, color }}>{value}</p>
            </div>
          ))}
        </div>

        {/* Chart */}
        <div style={{ background: '#fff', border: '1px solid #e2e8f0', borderRadius: 16, padding: 24, marginBottom: 28 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20, flexWrap: 'wrap', gap: 12 }}>
            <h2 style={{ margin: 0, fontSize: 17, fontWeight: 700 }}>Price History</h2>
            <div style={{ display: 'flex', gap: 6 }}>
              {(['7', '30', '120', '360'] as const).map(d => (
                <button key={d} className="range-btn" onClick={() => setTimeRange(d)} style={{
                  background: timeRange === d ? accentColor : '#f1f5f9',
                  color: timeRange === d ? '#fff' : '#64748b',
                }}>
                  {d === '7' ? '1W' : d === '30' ? '1M' : d === '120' ? '4M' : '1Y'}
                </button>
              ))}
            </div>
          </div>

          {chartData.length === 0 ? (
            <div style={{ height: 280, display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#94a3b8' }}>
              No data for this range
            </div>
          ) : (
            <ResponsiveContainer width="100%" height={300}>
              <LineChart data={chartData} margin={{ top: 5, right: 10, left: 5, bottom: 5 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" vertical={false} />
                <XAxis
                  dataKey="date"
                  tick={{ fill: '#94a3b8', fontSize: 11 }}
                  axisLine={false}
                  tickLine={false}
                  tickFormatter={(d: string) =>
                    new Date(d).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
                  }
                />
                <YAxis
                  tick={{ fill: '#94a3b8', fontSize: 11 }}
                  axisLine={false}
                  tickLine={false}
                  tickFormatter={(v: number) => `$${v.toFixed(0)}`}
                  domain={['auto', 'auto']}
                  width={65}
                />
                <Tooltip content={<CustomTooltip />} />
                <Line
                  type="monotone"
                  dataKey="close"
                  stroke={accentColor}
                  strokeWidth={2.5}
                  dot={false}
                  activeDot={{ r: 5, fill: accentColor, strokeWidth: 0 }}
                />
              </LineChart>
            </ResponsiveContainer>
          )}
        </div>

        {/* Performance breakdown */}
        <div style={{ background: '#fff', border: '1px solid #e2e8f0', borderRadius: 16, padding: 24 }}>
          <h2 style={{ margin: '0 0 4px', fontSize: 17, fontWeight: 700 }}>Performance Breakdown</h2>
          <p style={{ margin: '0 0 16px', fontSize: 13, color: '#94a3b8' }}>
            Calculated from last available price on {latest ? new Date(latest.date).toLocaleDateString() : '—'}
          </p>
          <div>
            {[
              { label: 'Current Price',   value: formatCurrency(latest?.close),         color: '#0f172a'              },
              { label: 'Adjusted Close',  value: formatCurrency(latest?.adjusted_close), color: '#0f172a'              },
              { label: '1-Day Return',    value: formatPercent(ret1d),                   color: getReturnColor(ret1d)   },
              { label: '30-Day Return',   value: formatPercent(ret30d),                  color: getReturnColor(ret30d)  },
              { label: '120-Day Return',  value: formatPercent(ret120d),                 color: getReturnColor(ret120d) },
              { label: '1-Year Return',   value: formatPercent(ret360d),                 color: getReturnColor(ret360d) },
            ].map(({ label, value, color }) => (
              <div key={label} className="perf-row">
                <span style={{ fontSize: 14, color: '#64748b' }}>{label}</span>
                <span style={{ fontSize: 15, fontWeight: 700, color }}>{value}</span>
              </div>
            ))}
          </div>
        </div>

      </div>
      {showModal && ticker && (
        <AddToPortfolioModal
          ticker={ticker}
          currentPrice={latest?.close ?? 0}
          onClose={() => setShowModal(false)}
          onSuccess={() => { setShowModal(false); navigate('/portfolio'); }}
        />
      )}
    </div>
  );
};

export default StockDetail;