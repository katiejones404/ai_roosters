import React, { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { login } from "./utils/auth.ts";
import "./login.css";

interface LoginFormData {
  email: string;
  password: string;
}

interface FormErrors {
  email?: string;
  password?: string;
  general?: string;
}

const Login: React.FC = () => {
  const navigate = useNavigate();
  const [formData, setFormData] = useState<LoginFormData>({
    email: "",
    password: "",
  });

  const [errors, setErrors] = useState<FormErrors>({});
  const [showPassword, setShowPassword] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const { name, value } = e.target;
    setFormData((prev) => ({
      ...prev,
      [name]: value,
    }));

    if (errors[name as keyof FormErrors]) {
      setErrors((prev) => ({
        ...prev,
        [name]: undefined,
        general: undefined,
      }));
    }
  };

  const validateForm = (): boolean => {
    const newErrors: FormErrors = {};

    if (!formData.email.trim()) newErrors.email = "Email is required";
    else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(formData.email)) {
      newErrors.email = "Please enter a valid email address";
    }

    if (!formData.password) {
      newErrors.password = "Password is required";
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!validateForm()) return;

    setIsSubmitting(true);

    try {
      await login(formData.email, formData.password);
      // alert("Login successful! Welcome back!");
      navigate("/dashboard", { replace: true });
    } catch (error: any) {
      const detail = error?.response?.data?.detail;

      setErrors({
        general:
          (Array.isArray(detail) ? detail[0]?.msg : detail) ||
          "Invalid credentials. Please try again.",
      });
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="login-container">
      <div className="login-background-shapes">
        <div className="login-shape login-shape-1"></div>
        <div className="login-shape login-shape-2"></div>
        <div className="login-shape login-shape-3"></div>
      </div>

      <div className="login-content">
        {/* Left Side - Branding */}
        <div className="login-left">
          <div className="login-branding">
            <h2 className="login-brand-name">
              Stock<span className="login-brand-highlight">Sense</span>
            </h2>
          </div>

          <div className="chart-container">
            <div className="chart-graphic">
              <svg viewBox="0 0 400 300" className="stock-chart">
                {/* Grid lines */}
                {[250, 200, 150, 100, 50].map((y, i) => (
                  <line
                    key={i}
                    x1="0"
                    y1={y}
                    x2="400"
                    y2={y}
                    stroke="rgba(16, 185, 129, 0.2)"
                    strokeWidth="1"
                  />
                ))}

                {/* Line chart */}
                <path
                  d="M 0 250 L 50 240 L 100 220 L 150 200 L 200 170 L 250 140 L 300 100 L 350 70 L 400 50"
                  fill="none"
                  stroke="url(#gradient)"
                  strokeWidth="3"
                  strokeLinecap="round"
                />

                <defs>
                  <linearGradient id="gradient" x1="0%" y1="0%" x2="100%" y2="0%">
                    <stop offset="0%" stopColor="#10b981" />
                    <stop offset="100%" stopColor="#34d399" />
                  </linearGradient>

                  <linearGradient id="barGradient" x1="0%" y1="0%" x2="0%" y2="100%">
                    <stop offset="0%" stopColor="#10b981" stopOpacity="0.8" />
                    <stop offset="100%" stopColor="#10b981" stopOpacity="0.3" />
                  </linearGradient>
                </defs>

                {/* Bars */}
                {[200, 180, 160, 130, 100, 70, 50].map((y, i) => (
                  <rect
                    key={i}
                    x={30 + i * 50}
                    y={y}
                    width="30"
                    height={250 - y}
                    fill="url(#barGradient)"
                  />
                ))}
              </svg>
            </div>

            <div className="stats-display">
              <div className="stat-item">
                <span className="stat-icon">📈</span>
                <div>
                  <div className="stat-value">+24.5%</div>
                  <div className="stat-label">Portfolio Growth</div>
                </div>
              </div>

              <div className="stat-item">
                <span className="stat-icon">💰</span>
                <div>
                  <div className="stat-value">$127.8K</div>
                  <div className="stat-label">Total Value</div>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Right Side - Login Form */}
        <div className="login-right">
          <div className="login-form-container">
            <h1 className="welcome-title">Welcome Back</h1>
            <p className="welcome-subtitle">
              Sign in to access your investment dashboard
            </p>

            {errors.general && (
              <div className="general-error">
                <span className="error-icon">⚠️</span>
                {errors.general}
              </div>
            )}

            <form onSubmit={handleSubmit} className="login-form" noValidate>
              <div className="form-group">
                <label htmlFor="email">Email Address</label>
                <div className="input-wrapper">
                  <input
                    type="text"
                    id="email"
                    name="email"
                    value={formData.email}
                    onChange={handleChange}
                    className={errors.email ? "error" : ""}
                    placeholder="Enter your email"
                    autoComplete="email"
                  />
                  <span className="input-icon">📧</span>
                </div>
                {errors.email && (
                  <span className="error-message">{errors.email}</span>
                )}
              </div>

              <div className="form-group">
                <label htmlFor="password">Password</label>
                <div className="input-wrapper">
                  <input
                    type={showPassword ? "text" : "password"}
                    id="password"
                    name="password"
                    value={formData.password}
                    onChange={handleChange}
                    className={errors.password ? "error" : ""}
                    placeholder="Enter your password"
                    autoComplete="current-password"
                  />
                  <button
                    type="button"
                    className="toggle-password"
                    onClick={() => setShowPassword(!showPassword)}
                  >
                    {showPassword ? "🙈" : "👁️"}
                  </button>
                </div>
                {errors.password && (
                  <span className="error-message">{errors.password}</span>
                )}
              </div>

              <button
                type="submit"
                className={`login-button ${isSubmitting ? "submitting" : ""}`}
                disabled={isSubmitting}
              >
                {isSubmitting ? (
                  <>
                    <span className="spinner"></span>
                    Signing in...
                  </>
                ) : (
                  "Sign in"
                )}
              </button>
            </form>

            <div className="signup-prompt">
              Don't have an account?{" "}
              <Link to="/signup" className="signup-link">
                Create one now
              </Link>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default Login;
