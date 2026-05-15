/*
 * PrivacyPolicy.tsx
 * Privacy Policy page for StockSense.
 */
import React from "react";
import { Link } from "react-router-dom";
import "./legal.css";

const PrivacyPolicy: React.FC = () => {
  return (
    <div className="legal-container">
      <div className="legal-card">
        <div className="legal-header">
          <div className="legal-branding">
            <Link to="/" className="legal-brand-name">
              Stock<span className="legal-brand-highlight">Sense</span>
            </Link>
          </div>
          <h1 className="legal-title">Privacy Policy</h1>
          <p className="legal-effective">Effective Date: April 1, 2025</p>
        </div>

        <div className="legal-body">
          <p className="legal-intro">
            Your privacy matters to us. This policy explains what information
            StockSense collects, how we use it, and your rights regarding your
            data.
          </p>

          <section className="legal-section">
            <h2>1. Information We Collect</h2>
            <p>When you create an account, we collect:</p>
            <ul>
              <li>Your email address</li>
              <li>Your username</li>
              <li>Your date of birth (to verify you are at least 18)</li>
              <li>An optional profile picture and phone number</li>
            </ul>
            <p>When you use the platform, we also collect:</p>
            <ul>
              <li>Portfolio data you enter (tickers, shares, cost basis)</li>
              <li>Net worth entries (assets and liabilities you add manually)</li>
              <li>Price alerts you configure</li>
              <li>Your watchlist and quiz results</li>
              <li>Login timestamps and streak data</li>
            </ul>
          </section>

          <section className="legal-section">
            <h2>2. How We Use Your Information</h2>
            <p>We use the information we collect to:</p>
            <ul>
              <li>Provide and operate the StockSense platform</li>
              <li>Personalize your dashboard and experience</li>
              <li>Send price alert emails based on your preferences</li>
              <li>Improve the platform's features and performance</li>
              <li>Maintain account security and prevent fraud</li>
            </ul>
            <p>
              We do not sell your personal information to third parties. We do
              not use your data to serve advertisements.
            </p>
          </section>

          <section className="legal-section">
            <h2>3. Data Storage and Security</h2>
            <p>
              Your data is stored in a PostgreSQL database hosted on Neon. We
              use industry-standard security practices including password hashing
              and JWT-based authentication. While we take reasonable precautions
              to protect your data, no system is completely secure and we cannot
              guarantee absolute security.
            </p>
          </section>

          <section className="legal-section">
            <h2>4. Third-Party Services</h2>
            <p>
              StockSense integrates with the following third-party services to
              deliver its functionality:
            </p>
            <ul>
              <li>
                <strong>OpenAI API</strong> — used to generate AI-powered news
                summaries
              </li>
              <li>
                <strong>yfinance</strong> — used to fetch stock price data from
                Yahoo Finance
              </li>
              <li>
                <strong>News APIs</strong> — used to ingest financial news
                articles
              </li>
              <li>
                <strong>Azure Container Apps</strong> — used to host backend
                services and scheduled jobs
              </li>
              <li>
                <strong>Vercel</strong> — used to host the frontend application
              </li>
            </ul>
            <p>
              These services have their own privacy policies. We encourage you
              to review them independently.
            </p>
          </section>

          <section className="legal-section">
            <h2>5. Cookies and Local Storage</h2>
            <p>
              StockSense uses browser localStorage to store your session token
              and quiz results locally on your device. We do not use tracking
              cookies or third-party advertising cookies.
            </p>
          </section>

          <section className="legal-section">
            <h2>6. Data Retention</h2>
            <p>
              We retain your account data for as long as your account is active.
              If you wish to delete your account and associated data, please
              contact us through our GitHub repository and we will process your
              request.
            </p>
          </section>

          <section className="legal-section">
            <h2>7. Children's Privacy</h2>
            <p>
              StockSense is not intended for users under the age of 18. We do
              not knowingly collect personal information from anyone under 18.
              If we become aware that a minor has created an account, we will
              delete that account promptly.
            </p>
          </section>

          <section className="legal-section">
            <h2>8. Your Rights</h2>
            <p>You have the right to:</p>
            <ul>
              <li>Access the personal data we hold about you</li>
              <li>Request correction of inaccurate data</li>
              <li>Request deletion of your account and data</li>
              <li>Opt out of marketing emails at any time</li>
            </ul>
            <p>
              To exercise any of these rights, please contact us through our
              GitHub repository.
            </p>
          </section>

          <section className="legal-section">
            <h2>9. Changes to This Policy</h2>
            <p>
              We may update this Privacy Policy from time to time. We will
              notify users of significant changes by updating the effective date
              at the top of this page. Continued use of the platform after
              changes constitutes acceptance of the updated policy.
            </p>
          </section>

          <section className="legal-section">
            <h2>10. Contact</h2>
            <p>
              For any privacy-related questions or requests, please reach out
              through our GitHub repository at{" "}
              <a
                href="https://github.com/SCCapstone/ai_roosters"
                target="_blank"
                rel="noopener noreferrer"
              >
                github.com/SCCapstone/ai_roosters
              </a>
              .
            </p>
          </section>
        </div>

        <div className="legal-footer">
          <Link to="/terms" className="legal-link">
            Terms of Service
          </Link>
          <span className="legal-divider">·</span>
          <Link to="/register" className="legal-link">
            Back to Sign Up
          </Link>
          <span className="legal-divider">·</span>
          <Link to="/" className="legal-link">
            Home
          </Link>
        </div>
      </div>
    </div>
  );
};

export default PrivacyPolicy;
