import React, { useEffect, useState } from "react";
import { getCurrentUser, logout } from "./utils/auth";
import { Link } from "react-router-dom";
import "./settings.css";

type TabType =
  | "account"
  | "security";

interface AccountFormData {
  name: string;
  username: string;
  email: string;
  bio: string;
  phone: string;
}

interface SecurityFormData {
  currentPassword: string;
  newPassword: string;
  confirmPassword: string;
  twoFactorEnabled: boolean;
}

interface NotificationSettings {
  emailNotifications: boolean;
  pushNotifications: boolean;
  marketAlerts: boolean;
  portfolioUpdates: boolean;
  weeklyReport: boolean;
}

const Settings: React.FC = () => {
  const [activeTab, setActiveTab] = useState<TabType>("account");
  const [isSaving, setIsSaving] = useState(false);
  const [successMessage, setSuccessMessage] = useState("");

  const [profileImage, setProfileImage] = useState<string>(
    "https://api.dicebear.com/7.x/avataaars/svg?seed=default"
  );

  // Account form state
  const [accountForm, setAccountForm] = useState<AccountFormData>({
    name: "John Doe",
    username: "johndoe",
    email: "john.doe@example.com",
    bio: "Passionate investor and tech enthusiast",
    phone: "+1 (555) 123-4567",
  });

  // Security form state
  const [securityForm, setSecurityForm] = useState<SecurityFormData>({
    currentPassword: "",
    newPassword: "",
    confirmPassword: "",
    twoFactorEnabled: false,
  });

  // Notification settings state
  const [notifications, setNotifications] = useState<NotificationSettings>({
    emailNotifications: true,
    pushNotifications: true,
    marketAlerts: true,
    portfolioUpdates: true,
    weeklyReport: false,
  });

  const [showPasswordFields, setShowPasswordFields] = useState({
    current: false,
    new: false,
    confirm: false,
  });

  // Load user info on mount
useEffect(() => {
  const loadUser = async () => {
    try {
      const user = await getCurrentUser();

      setAccountForm({
        name: user.name || "",
        username: user.username || "",
        email: user.email,
        bio: user.bio || "",
        phone: user.phone || "",
      });

      if (user.profileImage) {
        setProfileImage(user.profileImage);
      }
    } catch (err) {
      console.error("Failed to load user info", err);
    }
  };

  loadUser();
}, []);


  const handleAccountChange = (
    e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>
  ) => {
    setAccountForm((prev) => ({
      ...prev,
      [e.target.name]: e.target.value,
    }));
  };

  const handleSecurityChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const { name, value, type, checked } = e.target;
    setSecurityForm((prev) => ({
      ...prev,
      [name]: type === "checkbox" ? checked : value,
    }));
  };

  const handleNotificationChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setNotifications((prev) => ({
      ...prev,
      [e.target.name]: e.target.checked,
    }));
  };
  
  const handleSave = () => {
    setIsSaving(true);

    setTimeout(() => {
      setIsSaving(false);
      setSuccessMessage("Settings saved successfully!");

      // Clear success message after 3 seconds
      setTimeout(() => {
        setSuccessMessage("");
      }, 3000);
    }, 1000);
  };


  const handleLogout = () => {
    if (window.confirm("Are you sure you want to logout?")) {
      logout();
    }
  };

  return (
    <div className="settings-container">
      <div className="settings-background-shapes">
        <div className="settings-shape settings-shape-1"></div>
        <div className="settings-shape settings-shape-2"></div>
        <div className="settings-shape settings-shape-3"></div>
      </div>

      <div className="settings-content">
        {/* Sidebar Navigation */}
        <div className="settings-sidebar">
          <div className="settings-header">
            <h2>Settings</h2>
            <Link to="/" className="back-link">
              ← Back to Home
            </Link>
          </div>

          <nav className="settings-nav">
            <button
              className={`nav-tab ${activeTab === "account" ? "active" : ""}`}
              onClick={() => setActiveTab("account")}
            >
              <span className="tab-icon">👤</span>
              Account
            </button>
            <button
              className={`nav-tab ${activeTab === "security" ? "active" : ""}`}
              onClick={() => setActiveTab("security")}
            >
              <span className="tab-icon">🔒</span>
              Security
            </button>
          </nav>

          <button className="logout-button" onClick={handleLogout}>
            <span className="tab-icon">🚪</span>
            Logout
          </button>
        </div>

        {/* Main Content Area */}
        <div className="settings-main">
          {successMessage && (
            <div className="success-banner">
              <span className="success-icon">✅</span>
              {successMessage}
            </div>
          )}

          {/* Account Tab */}
          {activeTab === "account" && (
            <div className="tab-content">
              <div className="content-header">
                <h3>Account Information</h3>
                <p>Your profile details (read-only)</p>
              </div>

              <div className="profile-section">
                <div className="profile-image-container">
                  <img
                    src={profileImage}
                    alt="Profile"
                    className="profile-image"
                  />
                </div>

                <div className="profile-info">
                  <div className="info-item">
                    <span className="info-label">Account Status</span>
                    <span className="info-value status-active">Active</span>
                  </div>
                </div>
              </div>

              <div className="form-section">

                <div className="form-row">
                  <div className="form-group">
                    <label>Full Name</label>
                    <input
                      type="text"
                      value={accountForm.name}
                      readOnly
                      className="readonly-input"
                    />
                  </div>
                  <div className="form-group">
                    <label>Username</label>
                    <input
                      type="text"
                      value={accountForm.username}
                      readOnly
                      className="readonly-input"
                    />
                  </div>
                </div>

                <div className="form-row">
                  <div className="form-group">
                    <label>Email Address</label>
                    <input
                      type="email"
                      value={accountForm.email}
                      readOnly
                      className="readonly-input"
                    />
                  </div>
                  <div className="form-group">
                    <label>Phone Number</label>
                    <input
                      type="tel"
                      value={accountForm.phone}
                      readOnly
                      className="readonly-input"
                    />
                  </div>
                </div>

              </div>
            </div>
          )}

          {/* Security Tab */}
          {activeTab === "security" && (
            <div className="tab-content">
              <div className="content-header">
                <h3>Security Settings</h3>
                <p>Manage your password and authentication settings</p>
              </div>

              <div className="form-section">
                <div className="form-group">
                  <label htmlFor="currentPassword">Current Password</label>
                  <div className="password-input-wrapper">
                    <input
                      type={showPasswordFields.current ? "text" : "password"}
                      id="currentPassword"
                      name="currentPassword"
                      value={securityForm.currentPassword}
                      onChange={handleSecurityChange}
                      placeholder="Enter your current password"
                    />
                    <button
                      type="button"
                      className="toggle-password-btn"
                      onClick={() =>
                        setShowPasswordFields((prev) => ({
                          ...prev,
                          current: !prev.current,
                        }))
                      }
                    >
                      {showPasswordFields.current ? "🙈" : "👁️"}
                    </button>
                  </div>
                </div>

                <div className="form-group">
                  <label htmlFor="newPassword">New Password</label>
                  <div className="password-input-wrapper">
                    <input
                      type={showPasswordFields.new ? "text" : "password"}
                      id="newPassword"
                      name="newPassword"
                      value={securityForm.newPassword}
                      onChange={handleSecurityChange}
                      placeholder="Enter new password"
                    />
                    <button
                      type="button"
                      className="toggle-password-btn"
                      onClick={() =>
                        setShowPasswordFields((prev) => ({
                          ...prev,
                          new: !prev.new,
                        }))
                      }
                    >
                      {showPasswordFields.new ? "🙈" : "👁️"}
                    </button>
                  </div>
                </div>

                <div className="form-group">
                  <label htmlFor="confirmPassword">Confirm New Password</label>
                  <div className="password-input-wrapper">
                    <input
                      type={showPasswordFields.confirm ? "text" : "password"}
                      id="confirmPassword"
                      name="confirmPassword"
                      value={securityForm.confirmPassword}
                      onChange={handleSecurityChange}
                      placeholder="Confirm new password"
                    />
                    <button
                      type="button"
                      className="toggle-password-btn"
                      onClick={() =>
                        setShowPasswordFields((prev) => ({
                          ...prev,
                          confirm: !prev.confirm,
                        }))
                      }
                    >
                      {showPasswordFields.confirm ? "🙈" : "👁️"}
                    </button>
                  </div>
                </div>
              </div>

              <button
                onClick={handleSave}
                className="save-button"
                disabled={isSaving}
              >
                {isSaving ? (
                  <>
                    <span className="spinner"></span> Saving...
                  </>
                ) : (
                  "Update Security Settings"
                )}
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default Settings;
