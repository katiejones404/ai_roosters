/*
 * LandingPage.tsx
 * Public landing page introducing StockSense with feature highlights
 * and links to log in or create a new account.
 */
import { Link } from "react-router-dom";
import { FaChartLine, FaRobot, FaWallet } from "react-icons/fa";

export default function LandingPage() {
  return (
    <div className="app-container">
      <div className="home-background-shapes">
        <div className="home-shape home-shape-1"></div>
        <div className="home-shape home-shape-2"></div>
        <div className="home-shape home-shape-3"></div>
      </div>

      <div className="home-card landing-card">
        <div className="home-content">
          <h1>Welcome to StockSense</h1>
          <p>
            Make smarter investment decisions with real-time market insights,
            portfolio tracking, and AI-powered analytics.
          </p>

          <div className="nav-links">
            <Link to="/signup" className="nav-link nav-link-primary">
              Create Account
            </Link>
            <Link to="/login" className="nav-link nav-link-secondary">
              Sign In
            </Link>
          </div>

          <div className="features-section">
            <div className="features-grid landing-features-grid">
              <div className="feature-item">
                <div className="feature-icon" aria-hidden="true">
                  <FaChartLine />
                </div>
                <div className="feature-title">Live Analytics</div>
                <div className="feature-description">Real-time market insights</div>
              </div>

              <div className="feature-item">
                <div className="feature-icon" aria-hidden="true">
                  <FaWallet />
                </div>
                <div className="feature-title">Smart Tracking</div>
                <div className="feature-description">Monitor your portfolio</div>
              </div>

              <div className="feature-item">
                <div className="feature-icon" aria-hidden="true">
                  <FaRobot />
                </div>
                <div className="feature-title">AI Powered</div>
                <div className="feature-description">Intelligent insights</div>
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
