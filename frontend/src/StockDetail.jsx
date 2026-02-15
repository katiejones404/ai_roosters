import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import axios from 'axios';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
  Legend
} from 'recharts';

const StockDetail = () => {
  const { ticker } = useParams();
  const navigate = useNavigate();
  
  const [priceData, setPriceData] = useState([]);
  const [stockInfo, setStockInfo] = useState(null);
  const [sentimentData, setSentimentData] = useState(null);
  const [portfolioItem, setPortfolioItem] = useState(null);
  const [timeRange, setTimeRange] = useState('30');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (ticker) {
      fetchStockData();
    }
  }, [ticker, timeRange]);

  const fetchStockData = async () => {
    try {
      setLoading(true);
      const token = localStorage.getItem('access_token');
      
      // Calculate date range
      const endDate = new Date();
      const startDate = new Date();
      startDate.setDate(startDate.getDate() - parseInt(timeRange));

      // Fetch price history
      const priceResponse = await axios.get(
        `${import.meta.env.VITE_API_URL}/api/stocks/${ticker}/prices`,
        {
          params: {
            start_date: startDate.toISOString().split('T')[0],
            end_date: endDate.toISOString().split('T')[0]
          }
        }
      );

      setPriceData(priceResponse.data);

      // Get latest price info
      if (priceResponse.data.length > 0) {
        setStockInfo(priceResponse.data[priceResponse.data.length - 1]);
      }

      // Fetch sentiment snapshots
      try {
        const sentimentResponse = await axios.get(
          `${import.meta.env.VITE_API_URL}/api/stocks/${ticker}/snapshots`
        );
        if (sentimentResponse.data.length > 0) {
          setSentimentData(sentimentResponse.data[0]);
        }
      } catch (err) {
        console.log('No sentiment data available');
      }

      // Check if stock is in portfolio
      if (token) {
        try {
          const portfolioResponse = await axios.get(
            `${import.meta.env.VITE_API_URL}/api/portfolio/${ticker}`,
            {
              headers: { Authorization: `Bearer ${token}` }
            }
          );
          setPortfolioItem(portfolioResponse.data);
        } catch (err) {
          // Not in portfolio
          setPortfolioItem(null);
        }
      }

      setError(null);
    } catch (err) {
      console.error('Error fetching stock data:', err);
      setError('Failed to load stock data');
    } finally {
      setLoading(false);
    }
  };

  const addToPortfolio = async () => {
    const token = localStorage.getItem('access_token');
    if (!token) {
      navigate('/auth/login');
      return;
    }

    const quantity = prompt('Enter quantity:', '1');
    if (!quantity) return;

    const avgPrice = prompt('Enter purchase price:', stockInfo?.close || '0');
    if (!avgPrice) return;

    try {
      await axios.post(
        `${import.meta.env.VITE_API_URL}/api/portfolio`,
        {
          ticker: ticker,
          quantity: parseFloat(quantity),
          avg_price: parseFloat(avgPrice)
        },
        {
          headers: { Authorization: `Bearer ${token}` }
        }
      );

      alert('Added to portfolio successfully!');
      fetchStockData(); // Refresh to show portfolio item
    } catch (err) {
      console.error('Error adding to portfolio:', err);
      alert('Failed to add to portfolio');
    }
  };

  const removeFromPortfolio = async () => {
    if (!confirm(`Remove ${ticker} from portfolio?`)) return;

    const token = localStorage.getItem('access_token');
    try {
      await axios.delete(
        `${import.meta.env.VITE_API_URL}/api/portfolio/${ticker}`,
        {
          headers: { Authorization: `Bearer ${token}` }
        }
      );

      alert('Removed from portfolio');
      setPortfolioItem(null);
    } catch (err) {
      console.error('Error removing from portfolio:', err);
      alert('Failed to remove from portfolio');
    }
  };

  const formatCurrency = (value) => {
    if (value === null || value === undefined) return 'N/A';
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD'
    }).format(value);
  };

  const formatPercent = (value) => {
    if (value === null || value === undefined) return 'N/A';
    const sign = value >= 0 ? '+' : '';
    return `${sign}${(value * 100).toFixed(2)}%`;
  };

  const getReturnColor = (value) => {
    if (value === null || value === undefined) return 'text-gray-500';
    return value >= 0 ? 'text-green-600' : 'text-red-600';
  };

  const getSentimentBadge = (score) => {
    if (!score) return { text: 'Neutral', color: 'bg-gray-100 text-gray-800' };
    if (score > 0.05) return { text: 'Positive', color: 'bg-green-100 text-green-800' };
    if (score < -0.05) return { text: 'Negative', color: 'bg-red-100 text-red-800' };
    return { text: 'Neutral', color: 'bg-gray-100 text-gray-800' };
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto"></div>
          <p className="mt-4 text-gray-600">Loading {ticker}...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <p className="text-red-600 text-xl">{error}</p>
          <button
            onClick={() => navigate('/dashboard')}
            className="mt-4 px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700"
          >
            Back to Dashboard
          </button>
        </div>
      </div>
    );
  }

  const sentiment = getSentimentBadge(sentimentData?.sentiment_mean);

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white shadow-sm border-b">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
          <div className="flex justify-between items-center">
            <div className="flex items-center space-x-4">
              <button
                onClick={() => navigate(-1)}
                className="text-gray-600 hover:text-gray-900"
              >
                ← Back
              </button>
              <h1 className="text-2xl font-bold text-gray-900">{ticker}</h1>
            </div>
            <div className="flex space-x-2">
              {portfolioItem ? (
                <button
                  onClick={removeFromPortfolio}
                  className="px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700"
                >
                  Remove from Portfolio
                </button>
              ) : (
                <button
                  onClick={addToPortfolio}
                  className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
                >
                  Add to Portfolio
                </button>
              )}
            </div>
          </div>
        </div>
      </header>

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Stock Overview Cards */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-6 mb-8">
          <div className="bg-white rounded-lg shadow p-6">
            <p className="text-sm text-gray-600 mb-1">Current Price</p>
            <p className="text-2xl font-bold text-gray-900">
              {formatCurrency(stockInfo?.close)}
            </p>
          </div>

          <div className="bg-white rounded-lg shadow p-6">
            <p className="text-sm text-gray-600 mb-1">Today's Change</p>
            <p className={`text-2xl font-bold ${getReturnColor(stockInfo?.return_1d)}`}>
              {formatPercent(stockInfo?.return_1d)}
            </p>
          </div>

          <div className="bg-white rounded-lg shadow p-6">
            <p className="text-sm text-gray-600 mb-1">30-Day Return</p>
            <p className={`text-2xl font-bold ${getReturnColor(stockInfo?.return_30d)}`}>
              {formatPercent(stockInfo?.return_30d)}
            </p>
          </div>

          <div className="bg-white rounded-lg shadow p-6">
            <p className="text-sm text-gray-600 mb-1">Sentiment</p>
            <span className={`inline-block px-3 py-1 rounded-full text-sm font-semibold ${sentiment.color}`}>
              {sentiment.text}
            </span>
            {sentimentData?.num_articles && (
              <p className="text-xs text-gray-500 mt-2">
                Based on {sentimentData.num_articles} articles
              </p>
            )}
          </div>
        </div>

        {/* Portfolio Position (if in portfolio) */}
        {portfolioItem && (
          <div className="bg-blue-50 border border-blue-200 rounded-lg p-6 mb-8">
            <h3 className="text-lg font-semibold text-blue-900 mb-4">Your Position</h3>
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
              <div>
                <p className="text-sm text-blue-600">Quantity</p>
                <p className="text-xl font-bold text-blue-900">{portfolioItem.quantity}</p>
              </div>
              <div>
                <p className="text-sm text-blue-600">Average Price</p>
                <p className="text-xl font-bold text-blue-900">
                  {formatCurrency(portfolioItem.avg_price)}
                </p>
              </div>
              <div>
                <p className="text-sm text-blue-600">Cost Basis</p>
                <p className="text-xl font-bold text-blue-900">
                  {formatCurrency(portfolioItem.quantity * portfolioItem.avg_price)}
                </p>
              </div>
              <div>
                <p className="text-sm text-blue-600">Current Value</p>
                <p className="text-xl font-bold text-blue-900">
                  {formatCurrency(portfolioItem.quantity * (stockInfo?.close || 0))}
                </p>
              </div>
            </div>
          </div>
        )}

        {/* Price Chart */}
        <div className="bg-white rounded-lg shadow p-6 mb-8">
          <div className="flex justify-between items-center mb-6">
            <h2 className="text-xl font-semibold text-gray-900">Price History</h2>
            <div className="flex space-x-2">
              {['7', '30', '120', '360'].map((days) => (
                <button
                  key={days}
                  onClick={() => setTimeRange(days)}
                  className={`px-3 py-1 rounded ${
                    timeRange === days
                      ? 'bg-blue-600 text-white'
                      : 'bg-gray-200 text-gray-700 hover:bg-gray-300'
                  }`}
                >
                  {days === '7' ? '1W' : days === '30' ? '1M' : days === '120' ? '4M' : '1Y'}
                </button>
              ))}
            </div>
          </div>

          <ResponsiveContainer width="100%" height={400}>
            <LineChart data={priceData}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis
                dataKey="date"
                tickFormatter={(date) => new Date(date).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}
              />
              <YAxis domain={['auto', 'auto']} />
              <Tooltip
                formatter={(value) => formatCurrency(value)}
                labelFormatter={(date) => new Date(date).toLocaleDateString()}
              />
              <Legend />
              <Line
                type="monotone"
                dataKey="close"
                stroke="#2563eb"
                strokeWidth={2}
                dot={false}
                name="Close Price"
              />
            </LineChart>
          </ResponsiveContainer>
        </div>

        {/* Key Metrics */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {/* Performance Metrics */}
          <div className="bg-white rounded-lg shadow p-6">
            <h3 className="text-lg font-semibold text-gray-900 mb-4">Performance</h3>
            <div className="space-y-3">
              <div className="flex justify-between items-center">
                <span className="text-gray-600">1-Day Return</span>
                <span className={`font-semibold ${getReturnColor(stockInfo?.return_1d)}`}>
                  {formatPercent(stockInfo?.return_1d)}
                </span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-gray-600">30-Day Return</span>
                <span className={`font-semibold ${getReturnColor(stockInfo?.return_30d)}`}>
                  {formatPercent(stockInfo?.return_30d)}
                </span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-gray-600">120-Day Return</span>
                <span className={`font-semibold ${getReturnColor(stockInfo?.return_120d)}`}>
                  {formatPercent(stockInfo?.return_120d)}
                </span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-gray-600">360-Day Return</span>
                <span className={`font-semibold ${getReturnColor(stockInfo?.return_360d)}`}>
                  {formatPercent(stockInfo?.return_360d)}
                </span>
              </div>
            </div>
          </div>

          {/* Sentiment Metrics */}
          {sentimentData && (
            <div className="bg-white rounded-lg shadow p-6">
              <h3 className="text-lg font-semibold text-gray-900 mb-4">Sentiment Analysis</h3>
              <div className="space-y-3">
                <div className="flex justify-between items-center">
                  <span className="text-gray-600">Mean Sentiment</span>
                  <span className="font-semibold">{sentimentData.sentiment_mean?.toFixed(3)}</span>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-gray-600">Positive Articles</span>
                  <span className="font-semibold text-green-600">
                    {sentimentData.num_pos_articles} ({(sentimentData.pos_share * 100).toFixed(1)}%)
                  </span>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-gray-600">Negative Articles</span>
                  <span className="font-semibold text-red-600">
                    {sentimentData.num_neg_articles} ({(sentimentData.neg_share * 100).toFixed(1)}%)
                  </span>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-gray-600">Total Articles</span>
                  <span className="font-semibold">{sentimentData.num_articles}</span>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default StockDetail;