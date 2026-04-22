/*
 * CreateAccount.tsx
 * Registration page where new users create an account with an email address,
 * username, and password that meets the application strength requirements.
 */
import React, { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { register } from "./utils/auth";
import "./create_account.css";

interface FormData {
  email: string;
  username: string;
  password: string;
  retypePassword: string;
  dateOfBirth: string;
}

interface FormErrors {
  email?: string;
  username?: string;
  password?: string;
  retypePassword?: string;
  dateOfBirth?: string;
}

const CreateAccount: React.FC = () => {
  const navigate = useNavigate();

  const [formData, setFormData] = useState<FormData>({
    email: "",
    username: "",
    password: "",
    retypePassword: "",
    dateOfBirth: "",
  });

  const [errors, setErrors] = useState<FormErrors>({});
  const [showPassword, setShowPassword] = useState(false);
  const [showRetypePassword, setShowRetypePassword] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const validateEmail = (email: string): boolean =>
    /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);

  const validatePassword = (password: string): boolean =>
    password.length >= 8 && /[0-9!@#$%^&*(),.?":{}|<>]/.test(password);

  const isValidDate = (date: string): boolean => {
    const dateRegex =
      /^(0[1-9]|1[0-2])\/(0[1-9]|[12][0-9]|3[01])\/(19|20)\d{2}$/;
    if (!dateRegex.test(date)) return false;

    const [month, day, year] = date.split("/").map(Number);
    const parsed = new Date(year, month - 1, day);

    return (
      parsed.getFullYear() === year &&
      parsed.getMonth() === month - 1 &&
      parsed.getDate() === day
    );
  };

  const isOldEnough = (date: string): boolean => {
    const [month, day, year] = date.split("/").map(Number);
    const birthDate = new Date(year, month - 1, day);
    const today = new Date();
    let age = today.getFullYear() - birthDate.getFullYear();
    const monthDiff = today.getMonth() - birthDate.getMonth();

    if (
      monthDiff < 0 ||
      (monthDiff === 0 && today.getDate() < birthDate.getDate())
    ) {
      age -= 1;
    }

    return age >= 18;
  };

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const { name, value } = e.target;

    setFormData((prev) => ({ ...prev, [name]: value }));

    if (errors[name as keyof FormErrors]) {
      setErrors((prev) => ({ ...prev, [name]: undefined }));
    }
  };

  const handleDateChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    let value = e.target.value.replace(/\D/g, "");

    if (value.length >= 2) value = value.slice(0, 2) + "/" + value.slice(2);
    if (value.length >= 5) value = value.slice(0, 5) + "/" + value.slice(5, 9);

    setFormData((prev) => ({ ...prev, dateOfBirth: value }));

    if (errors.dateOfBirth) {
      setErrors((prev) => ({ ...prev, dateOfBirth: undefined }));
    }
  };

  const validateForm = (): boolean => {
    const newErrors: FormErrors = {};

    if (!formData.email) newErrors.email = "Email is required";
    else if (!validateEmail(formData.email))
      newErrors.email = "Please enter a valid email address";

    if (!formData.username) newErrors.username = "Username is required";
    else if (formData.username.length < 3)
      newErrors.username = "Username must be at least 3 characters";
    else if (!/^[a-zA-Z0-9_]+$/.test(formData.username))
      newErrors.username =
        "Username can only contain letters, numbers, and underscores";

    if (!formData.password) newErrors.password = "Password is required";
    else if (!validatePassword(formData.password))
      newErrors.password =
        "Password must be at least 8 characters and contain at least one number or special character";

    if (!formData.retypePassword)
      newErrors.retypePassword = "Please confirm your password";
    else if (formData.password !== formData.retypePassword)
      newErrors.retypePassword = "Passwords do not match";

    if (!formData.dateOfBirth) {
      newErrors.dateOfBirth = "Date of birth is required";
    } else if (!isValidDate(formData.dateOfBirth)) {
      newErrors.dateOfBirth = "Please enter a valid date (MM/DD/YYYY)";
    } else if (!isOldEnough(formData.dateOfBirth)) {
      newErrors.dateOfBirth = "You must be at least 18 years old to register";
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!validateForm()) return;

    setIsSubmitting(true);

    try {
      await register(
        formData.email,
        formData.username,
        formData.password,
        formData.retypePassword
      );

      navigate("/login", { replace: true });
    } catch (error: any) {
      const responseData = error.response?.data;

      if (error.response?.status === 422 && responseData?.detail) {
        const firstError = Array.isArray(responseData.detail)
          ? responseData.detail[0]?.msg
          : responseData.detail;
        setErrors({ retypePassword: firstError });
        return;
      }

      const detail =
        responseData?.detail ||
        responseData?.message ||
        (error.message && error.message !== "Network Error"
          ? error.message
          : null) ||
        "Something went wrong. Please try again.";

      if (
        typeof detail === "string" &&
        detail.toLowerCase().includes("email")
      ) {
        setErrors({ email: detail });
      } else if (
        typeof detail === "string" &&
        detail.toLowerCase().includes("username")
      ) {
        setErrors({ username: detail });
      } else if (
        typeof detail === "string" &&
        detail.toLowerCase().includes("password")
      ) {
        setErrors({ password: detail });
      } else {
        setErrors({
          email:
            typeof detail === "string"
              ? detail
              : "Registration failed. Please check your details and try again.",
        });
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="create-account-container">
      <div className="background-shapes">
        <div className="shape shape-1"></div>
        <div className="shape shape-2"></div>
        <div className="shape shape-3"></div>
      </div>

      <div className="create-account-card">
        <div className="header-section">
          <h1 className="main-title">You've made the right choice</h1>
          <p className="subtitle">Join thousands of smart investors today</p>
        </div>

        <form onSubmit={handleSubmit} className="account-form" noValidate>
          <div className="form-group">
            <label htmlFor="email">Email Address</label>
            <div className="input-wrapper">
              <input
                type="email"
                id="email"
                name="email"
                value={formData.email}
                onChange={handleChange}
                className={errors.email ? "error" : ""}
                placeholder="you@example.com"
              />
              <span className="input-icon">📧</span>
            </div>
            {errors.email && (
              <span className="error-message">{errors.email}</span>
            )}
          </div>

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
                placeholder="Letters, numbers, and underscores only"
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
                placeholder="Min 8 chars, include a number or special character"
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

          <div className="form-group">
            <label htmlFor="retypePassword">Retype Password</label>
            <div className="input-wrapper">
              <input
                type={showRetypePassword ? "text" : "password"}
                id="retypePassword"
                name="retypePassword"
                value={formData.retypePassword}
                onChange={handleChange}
                className={errors.retypePassword ? "error" : ""}
                placeholder="Confirm your password"
              />
              <button
                type="button"
                className="toggle-password"
                onClick={() => setShowRetypePassword(!showRetypePassword)}
              >
                {showRetypePassword ? "🙈" : "👁️"}
              </button>
            </div>
            {errors.retypePassword && (
              <span className="error-message">{errors.retypePassword}</span>
            )}
          </div>

          <div className="form-group">
            <label htmlFor="dateOfBirth">Date of Birth</label>
            <div className="input-wrapper">
              <input
                type="text"
                id="dateOfBirth"
                name="dateOfBirth"
                value={formData.dateOfBirth}
                onChange={handleDateChange}
                className={errors.dateOfBirth ? "error" : ""}
                placeholder="MM/DD/YYYY"
                maxLength={10}
              />
              <span className="input-icon">📅</span>
            </div>
            {errors.dateOfBirth && (
              <span className="error-message">{errors.dateOfBirth}</span>
            )}
          </div>

          <button
            type="submit"
            className={`submit-button ${isSubmitting ? "submitting" : ""}`}
            disabled={isSubmitting}
          >
            {isSubmitting ? (
              <>
                <span className="spinner"></span>
                Creating Account...
              </>
            ) : (
              "Create Account"
            )}
          </button>

          <p className="terms-text">
            By creating an account, you agree to our{" "}
            <Link to="/terms">Terms of Service</Link> and{" "}
            <Link to="/privacy">Privacy Policy</Link>
          </p>
        </form>

        <div className="login-prompt">
          Already have an account?{" "}
          <Link to="/login" className="login-link">
            Sign in here
          </Link>
        </div>

        <div className="branding">
          <span className="brand-name">
            Stock<span className="brand-highlight">Sense</span>
          </span>
        </div>
      </div>
    </div>
  );
};

export default CreateAccount;