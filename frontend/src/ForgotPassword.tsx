/*
 * ForgotPassword.tsx
 * Forgot password page where users submit their email address to receive
 * a time-limited password reset link.
 */
import React, { useState } from "react";
import { Link } from "react-router-dom";
import axios from "axios";
import "./login.css";

const API_URL = (import.meta.env.VITE_API_BASE_URL || "http://localhost:8000").replace(/\/$/, "");

const ForgotPassword: React.FC = () => {
  const [email, setEmail] = useState("");
  const [submitted, setSubmitted] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState("");

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!email.trim()) {
      setError("Please enter your email address.");
      return;
    }
    setError("");
    setIsSubmitting(true);
    try {
      await axios.post(`${API_URL}/api/auth/forgot-password`, { email });
    } catch {
      // Always show success to prevent email enumeration
    } finally {
      setIsSubmitting(false);
      setSubmitted(true);
    }
  };

  return (
    <div className="login-container">
      <div className="login-background-shapes">
        <div className="login-shape login-shape-1" />
        <div className="login-shape login-shape-2" />
        <div className="login-shape login-shape-3" />
      </div>

      <div className="login-content" style={{ gridTemplateColumns: "1fr", maxWidth: 480 }}>
        <div className="login-right" style={{ padding: "3rem" }}>
          <div className="login-form-container">
            <h1 className="welcome-title" style={{ fontSize: "2rem" }}>Forgot Password</h1>

            {submitted ? (
              <>
                <p className="welcome-subtitle" style={{ marginBottom: "1.5rem" }}>
                  If an account with that email exists, a password reset link has been
                  sent. Check your inbox and follow the link — it expires in 15 minutes.
                </p>
                <Link to="/login" className="login-button" style={{ textDecoration: "none", display: "flex", justifyContent: "center" }}>
                  Back to Login
                </Link>
              </>
            ) : (
              <>
                <p className="welcome-subtitle">
                  Enter your account email and we'll send you a reset link.
                </p>

                {error && (
                  <div className="general-error">
                    <span className="error-icon">⚠️</span>
                    {error}
                  </div>
                )}

                <form className="login-form" onSubmit={handleSubmit}>
                  <div className="form-group">
                    <label htmlFor="email">Email</label>
                    <div className="input-wrapper">
                      <input
                        id="email"
                        type="text"
                        placeholder="you@example.com"
                        value={email}
                        onChange={(e) => { setEmail(e.target.value); setError(""); }}
                        autoComplete="email"
                      />
                      <span className="input-icon">✉️</span>
                    </div>
                  </div>

                  <button
                    type="submit"
                    className={`login-button${isSubmitting ? " submitting" : ""}`}
                    disabled={isSubmitting}
                  >
                    {isSubmitting ? (
                      <><div className="spinner" /> Sending…</>
                    ) : (
                      "Send Reset Link"
                    )}
                  </button>
                </form>

                <div className="signup-prompt" style={{ marginTop: "1.5rem" }}>
                  <Link to="/login" className="signup-link">Back to Login</Link>
                </div>
              </>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default ForgotPassword;
