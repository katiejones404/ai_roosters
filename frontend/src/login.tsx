import React, { useState } from "react";
import { Link } from "react-router-dom";
import "./login.css";

interface LoginFormData {
  username: string;
  password: string;
}

interface FormErrors {
  username?: string;
  password?: string;
  general?: string;
}

const Login: React.FC = () => {
  const [formData, setFormData] = useState<LoginFormData>({
    username: "",
    password: "",
  });

  const [errors, setErrors] = useState<FormErrors>({});
  const [showPassword, setShowPassword] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [rememberMe, setRememberMe] = useState(false);

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const { name, value } = e.target;
    setFormData((prev) => ({
      ...prev,
      [name]: value,
    }));

    // Clear errors when user types
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

    if (!formData.username.trim()) {
      newErrors.username = "Username is required";
    }

    if (!formData.password) {
      newErrors.password = "Password is required";
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (validateForm()) {
      setIsSubmitting(true);

      // Simulate API call
      setTimeout(() => {
        // Simulate login validation
        if (
          formData.username.toLowerCase() === "demo" &&
          formData.password === "password"
        ) {
          alert("Login successful! Welcome back!");
          console.log("Login successful:", formData);
        } else {
          setErrors({
            general: "Invalid username or password. Please try again.",
          });
        }
        setIsSubmitting(false);
      }, 1500);
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
        {/* Left Side - Branding and Graphics */}
        <div className="login-left">
          <div className="login-branding">
            <h2 className="login-brand-name">
              Stock<span className="login-brand-highlight">Sense</span>
            </h2>
          </div>

          <div className="chart-container">
            <div className="chart-graphic">
              <svg viewBox="0 0 400 300" className="stock-chart">
                {/* Chart grid lines */}
                <line
                  x1="0"
                  y1="250"
                  x2="400"
                  y2="250"
                  stroke="rgba(16, 185, 129, 0.2)"
                  strokeWidth="1"
                />
                <line
                  x1="0"
                  y1="200"
                  x2="400"
                  y2="200"
                  stroke="rgba(16, 185, 129, 0.2)"
                  strokeWidth="1"
                />
                <line
                  x1="0"
                  y1="150"
                  x2="400"
                  y2="150"
                  stroke="rgba(16, 185, 129, 0.2)"
                  strokeWidth="1"
                />
                <line
                  x1="0"
                  y1="100"
                  x2="400"
                  y2="100"
                  stroke="rgba(16, 185, 129, 0.2)"
                  strokeWidth="1"
                />
                <line
                  x1="0"
                  y1="50"
                  x2="400"
                  y2="50"
                  stroke="rgba(16, 185, 129, 0.2)"
                  strokeWidth="1"
                />

                {/* Trend line */}
                <path
                  d="M 0 250 L 50 240 L 100 220 L 150 200 L 200 170 L 250 140 L 300 100 L 350 70 L 400 50"
                  fill="none"
                  stroke="url(#gradient)"
                  strokeWidth="3"
                  strokeLinecap="round"
                  className="chart-line"
                />

                {/* Gradient definition */}
                <defs>
                  <linearGradient
                    id="gradient"
                    x1="0%"
                    y1="0%"
                    x2="100%"
                    y2="0%"
                  >
                    <stop offset="0%" stopColor="#10b981" />
                    <stop offset="100%" stopColor="#34d399" />
                  </linearGradient>
                  <linearGradient
                    id="barGradient"
                    x1="0%"
                    y1="0%"
                    x2="0%"
                    y2="100%"
                  >
                    <stop offset="0%" stopColor="#10b981" stopOpacity="0.8" />
                    <stop offset="100%" stopColor="#10b981" stopOpacity="0.3" />
                  </linearGradient>
                </defs>

                {/* Bar chart elements */}
                <rect
                  x="30"
                  y="200"
                  width="30"
                  height="50"
                  fill="url(#barGradient)"
                  className="bar bar-1"
                />
                <rect
                  x="80"
                  y="180"
                  width="30"
                  height="70"
                  fill="url(#barGradient)"
                  className="bar bar-2"
                />
                <rect
                  x="130"
                  y="160"
                  width="30"
                  height="90"
                  fill="url(#barGradient)"
                  className="bar bar-3"
                />
                <rect
                  x="180"
                  y="130"
                  width="30"
                  height="120"
                  fill="url(#barGradient)"
                  className="bar bar-4"
                />
                <rect
                  x="230"
                  y="100"
                  width="30"
                  height="150"
                  fill="url(#barGradient)"
                  className="bar bar-5"
                />
                <rect
                  x="280"
                  y="70"
                  width="30"
                  height="180"
                  fill="url(#barGradient)"
                  className="bar bar-6"
                />
                <rect
                  x="330"
                  y="50"
                  width="30"
                  height="200"
                  fill="url(#barGradient)"
                  className="bar bar-7"
                />
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
            <h1 className="welcome-title">Welcome</h1>
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
                <label htmlFor="username">Username</label>
                <div className="input-wrapper">
                  <input
                    type="text"
                    id="username"
                    name="username"
                    value={formData.username}
                    onChange={handleChange}
                    className={errors.username ? "error" : ""}
                    placeholder="Enter your username"
                    autoComplete="username"
                  />
                  <span className="input-icon">👤</span>
                </div>
                {errors.username && (
                  <span className="error-message">{errors.username}</span>
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
                    aria-label="Toggle password visibility"
                  >
                    {showPassword ? "🙈" : "👁️"}
                  </button>
                </div>
                {errors.password && (
                  <span className="error-message">{errors.password}</span>
                )}
              </div>

              <div className="form-options">
                <label className="remember-me">
                  <input
                    type="checkbox"
                    checked={rememberMe}
                    onChange={(e) => setRememberMe(e.target.checked)}
                  />
                  <span>Remember me</span>
                </label>
                <Link to="/forgot-password" className="forgot-link">
                  Forgot password?
                </Link>
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
              </Link>{" "}
            </div>

            <div className="demo-credentials">
              <small>
                Demo: username: <strong>demo</strong>, password:{" "}
                <strong>password</strong>
              </small>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default Login;
