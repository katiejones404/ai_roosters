import React, { useState } from "react";
import { Link } from "react-router-dom";
import "./settings.css";

type TabType =
  | "account"
  | "security"
  | "notifications"
  | "support"
  | "configuration";

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
    "https://api.dicebear.com/7.x/avataaars/svg?seed=John"
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

  const handleImageUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      const reader = new FileReader();
      reader.onloadend = () => {
        setProfileImage(reader.result as string);
      };
      reader.readAsDataURL(file);
    }
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
      alert("Logging out...");
      // Add logout logic here
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
            <button
              className={`nav-tab ${
                activeTab === "notifications" ? "active" : ""
              }`}
              onClick={() => setActiveTab("notifications")}
            >
              <span className="tab-icon">🔔</span>
              Notifications
            </button>
            <button
              className={`nav-tab ${activeTab === "support" ? "active" : ""}`}
              onClick={() => setActiveTab("support")}
            >
              <span className="tab-icon">💬</span>
              Support
            </button>
            <button
              className={`nav-tab ${
                activeTab === "configuration" ? "active" : ""
              }`}
              onClick={() => setActiveTab("configuration")}
            >
              <span className="tab-icon">⚙️</span>
              Configuration
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
                <h3>Account Settings</h3>
                <p>Manage your personal information and profile</p>
              </div>

              <div className="profile-section">
                <div className="profile-image-container">
                  <img
                    src={profileImage}
                    alt="Profile"
                    className="profile-image"
                  />
                  <label htmlFor="profile-upload" className="upload-button">
                    📷 Change Photo
                  </label>
                  <input
                    type="file"
                    id="profile-upload"
                    accept="image/*"
                    onChange={handleImageUpload}
                    style={{ display: "none" }}
                  />
                </div>

                <div className="profile-info">
                  <div className="info-item">
                    <span className="info-label">Member Since</span>
                    <span className="info-value">January 2024</span>
                  </div>
                  <div className="info-item">
                    <span className="info-label">Account Status</span>
                    <span className="info-value status-active">Active</span>
                  </div>
                </div>
              </div>

              <div className="form-section">
                <div className="form-row">
                  <div className="form-group">
                    <label htmlFor="name">Full Name</label>
                    <input
                      type="text"
                      id="name"
                      name="name"
                      value={accountForm.name}
                      onChange={handleAccountChange}
                      placeholder="Enter your full name"
                    />
                  </div>
                  <div className="form-group">
                    <label htmlFor="username">Username</label>
                    <input
                      type="text"
                      id="username"
                      name="username"
                      value={accountForm.username}
                      onChange={handleAccountChange}
                      placeholder="Choose a username"
                    />
                  </div>
                </div>

                <div className="form-row">
                  <div className="form-group">
                    <label htmlFor="email">Email Address</label>
                    <input
                      type="email"
                      id="email"
                      name="email"
                      value={accountForm.email}
                      onChange={handleAccountChange}
                      placeholder="your.email@example.com"
                    />
                  </div>
                  <div className="form-group">
                    <label htmlFor="phone">Phone Number</label>
                    <input
                      type="tel"
                      id="phone"
                      name="phone"
                      value={accountForm.phone}
                      onChange={handleAccountChange}
                      placeholder="+1 (555) 123-4567"
                    />
                  </div>
                </div>

                <div className="form-group">
                  <label htmlFor="bio">Bio</label>
                  <textarea
                    id="bio"
                    name="bio"
                    value={accountForm.bio}
                    onChange={handleAccountChange}
                    placeholder="Tell us about yourself..."
                    rows={4}
                  />
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
                  "Save Changes"
                )}
              </button>
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

                <div className="security-option">
                  <div className="option-info">
                    <h4>Two-Factor Authentication</h4>
                    <p>Add an extra layer of security to your account</p>
                  </div>
                  <label className="toggle-switch">
                    <input
                      type="checkbox"
                      name="twoFactorEnabled"
                      checked={securityForm.twoFactorEnabled}
                      onChange={handleSecurityChange}
                    />
                    <span className="toggle-slider"></span>
                  </label>
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

          {/* Notifications Tab */}
          {activeTab === "notifications" && (
            <div className="tab-content">
              <div className="content-header">
                <h3>Notification Preferences</h3>
                <p>Choose what updates you want to receive</p>
              </div>

              <div className="notifications-list">
                <div className="notification-item">
                  <div className="notification-info">
                    <h4>📧 Email Notifications</h4>
                    <p>Receive updates via email</p>
                  </div>
                  <label className="toggle-switch">
                    <input
                      type="checkbox"
                      name="emailNotifications"
                      checked={notifications.emailNotifications}
                      onChange={handleNotificationChange}
                    />
                    <span className="toggle-slider"></span>
                  </label>
                </div>

                <div className="notification-item">
                  <div className="notification-info">
                    <h4>📱 Push Notifications</h4>
                    <p>Get instant alerts on your device</p>
                  </div>
                  <label className="toggle-switch">
                    <input
                      type="checkbox"
                      name="pushNotifications"
                      checked={notifications.pushNotifications}
                      onChange={handleNotificationChange}
                    />
                    <span className="toggle-slider"></span>
                  </label>
                </div>

                <div className="notification-item">
                  <div className="notification-info">
                    <h4>🔔 Market Alerts</h4>
                    <p>Real-time alerts for significant market movements</p>
                  </div>
                  <label className="toggle-switch">
                    <input
                      type="checkbox"
                      name="marketAlerts"
                      checked={notifications.marketAlerts}
                      onChange={handleNotificationChange}
                    />
                    <span className="toggle-slider"></span>
                  </label>
                </div>

                <div className="notification-item">
                  <div className="notification-info">
                    <h4>💼 Portfolio Updates</h4>
                    <p>Daily summaries of your portfolio performance</p>
                  </div>
                  <label className="toggle-switch">
                    <input
                      type="checkbox"
                      name="portfolioUpdates"
                      checked={notifications.portfolioUpdates}
                      onChange={handleNotificationChange}
                    />
                    <span className="toggle-slider"></span>
                  </label>
                </div>

                <div className="notification-item">
                  <div className="notification-info">
                    <h4>📊 Weekly Report</h4>
                    <p>Comprehensive weekly analysis of your investments</p>
                  </div>
                  <label className="toggle-switch">
                    <input
                      type="checkbox"
                      name="weeklyReport"
                      checked={notifications.weeklyReport}
                      onChange={handleNotificationChange}
                    />
                    <span className="toggle-slider"></span>
                  </label>
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
                  "Save Preferences"
                )}
              </button>
            </div>
          )}

          {/* Support Tab */}
          {activeTab === "support" && (
            <div className="tab-content">
              <div className="content-header">
                <h3>Support & Help</h3>
                <p>Get help and access resources</p>
              </div>

              <div className="support-grid">
                <div className="support-card">
                  <div className="support-icon">📚</div>
                  <h4>Documentation</h4>
                  <p>Browse our comprehensive guides</p>
                  <button className="support-action">View Docs</button>
                </div>

                <div className="support-card">
                  <div className="support-icon">💬</div>
                  <h4>Live Chat</h4>
                  <p>Chat with our support team</p>
                  <button className="support-action">Start Chat</button>
                </div>

                <div className="support-card">
                  <div className="support-icon">📧</div>
                  <h4>Email Support</h4>
                  <p>Send us a detailed message</p>
                  <button className="support-action">Send Email</button>
                </div>

                <div className="support-card">
                  <div className="support-icon">❓</div>
                  <h4>FAQ</h4>
                  <p>Find answers to common questions</p>
                  <button className="support-action">View FAQ</button>
                </div>
              </div>

              <div className="contact-info">
                <h4>Contact Information</h4>
                <p>📞 Phone: 1-800-STOCKSENSE</p>
                <p>📧 Email: support@stocksense.com</p>
                <p>🕐 Hours: Monday - Friday, 9AM - 6PM EST</p>
              </div>
            </div>
          )}

          {/* Configuration Tab */}
          {activeTab === "configuration" && (
            <div className="tab-content">
              <div className="content-header">
                <h3>App Configuration</h3>
                <p>Customize your StockSense experience</p>
              </div>

              <div className="config-section">
                <h4>Appearance</h4>
                <div className="config-options">
                  <label className="radio-option">
                    <input type="radio" name="theme" value="light" />
                    <span>☀️ Light Mode</span>
                  </label>
                  <label className="radio-option">
                    <input
                      type="radio"
                      name="theme"
                      value="dark"
                      defaultChecked
                    />
                    <span>🌙 Dark Mode</span>
                  </label>
                  <label className="radio-option">
                    <input type="radio" name="theme" value="auto" />
                    <span>🔄 Auto</span>
                  </label>
                </div>
              </div>

              <div className="config-section">
                <h4>Language & Region</h4>
                <div className="form-group">
                  <label htmlFor="language">Language</label>
                  <select id="language" name="language">
                    <option value="en">English</option>
                    <option value="es">Español</option>
                    <option value="fr">Français</option>
                    <option value="de">Deutsch</option>
                  </select>
                </div>
                <div className="form-group">
                  <label htmlFor="currency">Currency</label>
                  <select id="currency" name="currency">
                    <option value="usd">USD ($)</option>
                    <option value="eur">EUR (€)</option>
                    <option value="gbp">GBP (£)</option>
                    <option value="jpy">JPY (¥)</option>
                  </select>
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
                  "Save Configuration"
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
