import { BrowserRouter, Routes, Route, Link, useLocation} from "react-router-dom";
import CreateAccount from "./create_account.tsx";
import Login from "./login.tsx";
import Settings from "./settings.tsx"; 
import "./App.css";
import Dashboard from "./Dashboard";
import Navbar from "./components/Navbar.tsx";

import { useEffect, useState } from "react";
import { fetchAllStockIndicators } from "./utils/sentiment";
import type { StockIndicators } from "./utils/sentiment";
import { StockSentimentCard } from "./SentimentIndicators";
function Home() {

  const [indicators, setIndicators] = useState<StockIndicators[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const loadIndicators = async () => {
      try {
        const data = await fetchAllStockIndicators();

        // If you only want specific stocks, filter here, e.g. BP + RELIANCE:
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
            portfolio tracking, and AI-powered analytics. Join thousands of
            investors who trust StockSense.
          </p>

          <div className="nav-links">
            <a href="/signup" className="nav-link nav-link-primary">🚀 Create Account</a>
            <a href="/login" className="nav-link nav-link-secondary">🔐 Sign In</a>
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

function App() {
  return (
    <BrowserRouter>
      <AppContent />
    </BrowserRouter>
  );
}

function AppContent() {
  const location = useLocation();
  const hideNavbar =
    location.pathname === "/login" || location.pathname === "/signup" || location.pathname === "/";
  return (
    <>
      {!hideNavbar && <Navbar />}
      
      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/signup" element={<CreateAccount />} />
        <Route path="/login" element={<Login />} />

        {/* Routes that use the header layout */}
        <Route element={<Layout/>}>
          <Route path="/dashboard" element={<Dashboard />} />
          <Route path="/settings" element={<Settings />} />
          
        </Route>

      </Routes>
    </>
  );
}
export default App;
