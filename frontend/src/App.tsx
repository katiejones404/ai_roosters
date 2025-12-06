import { BrowserRouter, Routes, Route, Link, useLocation } from "react-router-dom";
import { useEffect, useState } from "react";

import CreateAccount from "./create_account";
import Login from "./login";
import Settings from "./settings";
import Dashboard from "./Dashboard";
import Layout from "./layout"; 
import Navbar from "./components/Navbar";

import "./App.css";

import { fetchAllStockIndicators } from "./utils/sentiment";
import type { StockIndicators } from "./utils/sentiment";
import { StockSentimentCard } from "./SentimentIndicators";


// ---------------------- HOME PAGE ----------------------
function Home() {
  const [indicators, setIndicators] = useState<StockIndicators[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const loadIndicators = async () => {
      try {
        const data = await fetchAllStockIndicators();

        // Show only BP + RELIANCE
        const filtered = data.filter((item) =>
          ["BP", "RELIANCE"].includes(item.ticker)
        );

        setIndicators(filtered);
      } catch (err) {
        console.error(err);
        setError("Failed to load sentiment indicators");
      } finally {
        setLoading(false);
      }
    };

    loadIndicators();
  }, []);

  return (
    <div className="app-container">
      <div className="home-background-shapes">
        <div className="home-shape home-shape-1"></div>
        <div className="home-shape home-shape-2"></div>
        <div className="home-shape home-shape-3"></div>
      </div>

      <div className="home-card">
        <div className="home-content">
          <h1>Welcome to StockSense</h1>
          <p>
            Make smarter investment decisions with real-time market insights,
            portfolio tracking, and AI-powered analytics.
          </p>

          <div className="nav-links">
            <Link to="/signup" className="nav-link nav-link-primary">
              🚀 Create Account
            </Link>
            <Link to="/login" className="nav-link nav-link-secondary">
              🔐 Sign In
            </Link>
          </div>

          <div className="features-section">
            <div className="features-grid">
              <div className="feature-item">
                <div className="feature-icon">📊</div>
                <div className="feature-title">Live Analytics</div>
                <div className="feature-description">
                  Real-time market data and insights
                </div>
              </div>
              <div className="feature-item">
                <div className="feature-icon">🎯</div>
                <div className="feature-title">Smart Tracking</div>
                <div className="feature-description">
                  Monitor your portfolio effortlessly
                </div>
              </div>
              <div className="feature-item">
                <div className="feature-icon">🤖</div>
                <div className="feature-title">AI Powered</div>
                <div className="feature-description">
                  Intelligent recommendations
                </div>
              </div>
            </div>
          </div>

          <div className="sentiment-section">
            <div className="sentiment-title">Current Market Sentiment</div>

            {loading && <p>Loading sentiment...</p>}
            {error && <p className="sentiment-error">{error}</p>}

            {!loading && !error && (
              <div className="sentiment-grid">
                {indicators.map((stock) => (
                  <StockSentimentCard key={stock.ticker} data={stock} />
                ))}
              </div>
            )}
          </div>
        </div>

        <div className="home-branding">
          <div className="home-brand-name">
            Stock<span className="home-brand-highlight">Sense</span>
          </div>
          <div className="home-tagline">Smart investing made simple</div>
        </div>
      </div>
    </div>
  );
}


// ---------------------- APP WRAPPER ----------------------
function App() {
  return (
    <BrowserRouter>
      <AppContent />
    </BrowserRouter>
  );
}


// ---------------------- CONDITIONAL NAVBAR + ROUTES ----------------------
function AppContent() {
  const location = useLocation();

  // Hide navbar ONLY on login/signup/home
  const hideNavbar =
    location.pathname === "/login" ||
    location.pathname === "/signup" ||
    location.pathname === "/";

  return (
    <>
      {!hideNavbar && <Navbar />}

      <Routes>
        {/* Public routes */}
        <Route path="/" element={<Home />} />
        <Route path="/signup" element={<CreateAccount />} />
        <Route path="/login" element={<Login />} />

        {/* Protected layout-based routes */}
        <Route element={<Layout />}>
          <Route path="/dashboard" element={<Dashboard />} />
          <Route path="/settings" element={<Settings />} />
        </Route>

        {/* Catch-all fallback (optional) */}
        <Route path="*" element={<Home />} />
      </Routes>
    </>
  );
}

export default App;
