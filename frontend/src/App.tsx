import { BrowserRouter, Routes, Route, Link } from "react-router-dom";
import CreateAccount from "./create_account.tsx";
import Login from "./login.tsx";
import Settings from "./settings.tsx";
import "./App.css";

function Home() {
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
      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/signup" element={<CreateAccount />} />
        <Route path="/login" element={<Login />} />
        <Route path="/settings" element={<Settings />} />
      </Routes>
    </BrowserRouter>
  );
}

export default App;
