/*
 * ResetPassword.tsx
 * Password reset page where users set a new password using a time-limited
 * token delivered via email. Redirects to login on success.
 */
import React, { useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import axios from "axios";
import "./login.css";

const API_URL = (import.meta.env.VITE_API_BASE_URL || "http://localhost:8000").replace(/\/$/, "");

const ResetPassword: React.FC = () => {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const token = searchParams.get("token") || "";

  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [showNew, setShowNew] = useState(false);
  const [showConfirm, setShowConfirm] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState(false);

  if (!token) {
    return (
      <div className="login-container">
        <div className="login-background-shapes">
          <div className="login-shape login-shape-1" />
          <div className="login-shape login-shape-2" />
        </div>
        <div className="login-content" style={{ gridTemplateColumns: "1fr", maxWidth: 480 }}>
          <div className="login-right" style={{ padding: "3rem" }}>
            <div className="login-form-container">
              <h1 className="welcome-title" style={{ fontSize: "2rem" }}>Invalid Link</h1>
              <p className="welcome-subtitle">
                This password reset link is missing or invalid. Please request a new one.
              </p>
              <Link to="/forgot-password" className="login-button" style={{ textDecoration: "none", display: "flex", justifyContent: "center" }}>
                Request New Link
              </Link>
            </div>
          </div>
        </div>
      </div>
    );
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (newPassword.length < 8) {
      setError("Password must be at least 8 characters.");
      return;
    }
    if (!/[0-9!@#$%^&*(),.?":{}|<>]/.test(newPassword)) {
      setError("Password must contain at least one number or special character.");
      return;
    }
    if (newPassword !== confirmPassword) {
      setError("Passwords do not match.");
      return;
    }
    setError("");
    setIsSubmitting(true);
    try {
      await axios.post(`${API_URL}/api/auth/reset-password`, {
        token,
        new_password: newPassword,
      });
      setSuccess(true);
      setTimeout(() => navigate("/login"), 3000);
    } catch (err: any) {
      const detail = err?.response?.data?.detail;
      setError(detail || "Reset failed. The link may have expired. Please request a new one.");
    } finally {
      setIsSubmitting(false);
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
            <h1 className="welcome-title" style={{ fontSize: "2rem" }}>Reset Password</h1>

            {success ? (
              <>
                <p className="welcome-subtitle" style={{ marginBottom: "1.5rem" }}>
                  Your password has been updated. Redirecting you to login…
                </p>
                <Link to="/login" className="login-button" style={{ textDecoration: "none", display: "flex", justifyContent: "center" }}>
                  Go to Login
                </Link>
              </>
            ) : (
              <>
                <p className="welcome-subtitle">Enter your new password below.</p>

                {error && (
                  <div className="general-error">
                    <span className="error-icon">⚠️</span>
                    {error}
                  </div>
                )}

                <form className="login-form" onSubmit={handleSubmit}>
                  <div className="form-group">
                    <label htmlFor="new-password">New Password</label>
                    <div className="input-wrapper">
                      <input
                        id="new-password"
                        type={showNew ? "text" : "password"}
                        placeholder="Min. 8 chars with a number or symbol"
                        value={newPassword}
                        onChange={(e) => { setNewPassword(e.target.value); setError(""); }}
                        autoComplete="new-password"
                      />
                      <button
                        type="button"
                        className="toggle-password"
                        onClick={() => setShowNew((v) => !v)}
                        aria-label={showNew ? "Hide password" : "Show password"}
                      >
                        {showNew ? "🙈" : "👁️"}
                      </button>
                    </div>
                  </div>

                  <div className="form-group">
                    <label htmlFor="confirm-password">Confirm Password</label>
                    <div className="input-wrapper">
                      <input
                        id="confirm-password"
                        type={showConfirm ? "text" : "password"}
                        placeholder="Repeat new password"
                        value={confirmPassword}
                        onChange={(e) => { setConfirmPassword(e.target.value); setError(""); }}
                        autoComplete="new-password"
                      />
                      <button
                        type="button"
                        className="toggle-password"
                        onClick={() => setShowConfirm((v) => !v)}
                        aria-label={showConfirm ? "Hide password" : "Show password"}
                      >
                        {showConfirm ? "🙈" : "👁️"}
                      </button>
                    </div>
                  </div>

                  <button
                    type="submit"
                    className={`login-button${isSubmitting ? " submitting" : ""}`}
                    disabled={isSubmitting}
                  >
                    {isSubmitting ? (
                      <><div className="spinner" /> Updating…</>
                    ) : (
                      "Set New Password"
                    )}
                  </button>
                </form>

                <div className="signup-prompt" style={{ marginTop: "1.5rem" }}>
                  <Link to="/forgot-password" className="signup-link">Request a new link</Link>
                </div>
              </>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default ResetPassword;
