import React, { useState } from "react";
import { Link } from "react-router-dom";
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

  const validateEmail = (email: string): boolean => {
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    return emailRegex.test(email);
  };

  const validatePassword = (password: string): boolean => {
    return password.length >= 8;
  };

  const validateDateOfBirth = (date: string): boolean => {
    const dateRegex =
      /^(0[1-9]|1[0-2])\/(0[1-9]|[12][0-9]|3[01])\/(19|20)\d{2}$/;
    if (!dateRegex.test(date)) return false;

    const [month, day, year] = date.split("/").map(Number);
    const birthDate = new Date(year, month - 1, day);
    const today = new Date();
    const age = today.getFullYear() - birthDate.getFullYear();

    return age >= 18;
  };

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const { name, value } = e.target;
    setFormData((prev) => ({
      ...prev,
      [name]: value,
    }));

    // Clear error when user starts typing
    if (errors[name as keyof FormErrors]) {
      setErrors((prev) => ({
        ...prev,
        [name]: undefined,
      }));
    }
  };

  const handleDateChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    let value = e.target.value.replace(/\D/g, "");

    if (value.length >= 2) {
      value = value.slice(0, 2) + "/" + value.slice(2);
    }
    if (value.length >= 5) {
      value = value.slice(0, 5) + "/" + value.slice(5, 9);
    }

    setFormData((prev) => ({
      ...prev,
      dateOfBirth: value,
    }));

    if (errors.dateOfBirth) {
      setErrors((prev) => ({
        ...prev,
        dateOfBirth: undefined,
      }));
    }
  };

  const validateForm = (): boolean => {
    const newErrors: FormErrors = {};

    if (!formData.email) {
      newErrors.email = "Email is required";
    } else if (!validateEmail(formData.email)) {
      newErrors.email = "Please enter a valid email address";
    }

    if (!formData.username) {
      newErrors.username = "Username is required";
    } else if (formData.username.length < 3) {
      newErrors.username = "Username must be at least 3 characters";
    }

    if (!formData.password) {
      newErrors.password = "Password is required";
    } else if (!validatePassword(formData.password)) {
      newErrors.password = "Password must be at least 8 characters";
    }

    if (!formData.retypePassword) {
      newErrors.retypePassword = "Please confirm your password";
    } else if (formData.password !== formData.retypePassword) {
      newErrors.retypePassword = "Passwords do not match";
    }

    if (!formData.dateOfBirth) {
      newErrors.dateOfBirth = "Date of birth is required";
    } else if (!validateDateOfBirth(formData.dateOfBirth)) {
      newErrors.dateOfBirth = "You must be at least 18 years old";
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (validateForm()) {
      setIsSubmitting(true);

      try {
        // Call real backend API
        await register(formData.email, formData.username, formData.password);

        alert("Account created successfully! Please login.");
        // Redirect to login page
        window.location.href = "/login";
      } catch (error: any) {
        // Show error from backend
        setErrors({
          email:
            error.response?.data?.detail ||
            "Registration failed. Please try again.",
        });
      } finally {
        setIsSubmitting(false);
      }
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
                placeholder="Choose a unique username"
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
                placeholder="At least 8 characters"
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
                aria-label="Toggle password visibility"
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
            <a href="#terms">Terms of Service</a> and{" "}
            <a href="#privacy">Privacy Policy</a>
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
