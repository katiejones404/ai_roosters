/*
 * Settings.tsx
 * User settings page for managing account information, updating the password,
 * and configuring notification preferences.
 */
import React, { useEffect, useState, useRef } from "react";
import {
  getCurrentUser,
  logout,
  deleteAccount,
  updateProfilePicture,
  updateProfile,
  changePassword,
  getNotificationPreferences,
  updateNotificationPreferences,
  type NotificationPreferences,
} from "./utils/auth";
import { Link, useNavigate } from "react-router-dom";
import "./settings.css";

type TabType = "account" | "security" | "notifications";

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
}

type NotificationSettings = NotificationPreferences;
const DEFAULT_PROFILE_PICTURE = "/default_pfp.jpg";

const Settings: React.FC = () => {
  const navigate = useNavigate();
  const [activeTab, setActiveTab] = useState<TabType>("account");
  const [isSaving, setIsSaving] = useState(false);
  const [successMessage, setSuccessMessage] = useState("");
  const [errorMessage, setErrorMessage] = useState("");
  const [isSavingPassword, setIsSavingPassword] = useState(false);
  const [passwordError, setPasswordError] = useState("");
  const [passwordSuccess, setPasswordSuccess] = useState("");
  const [notificationError, setNotificationError] = useState("");
  const [isSavingNotifications, setIsSavingNotifications] = useState(false);

  const [profileImage, setProfileImage] = useState<string>(
    DEFAULT_PROFILE_PICTURE
  );
  const [pictureUploading, setPictureUploading] = useState(false);
  const [pictureError, setPictureError] = useState("");
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  const [deletePassword, setDeletePassword] = useState("");
  const [deleteError, setDeleteError] = useState("");

  const fileInputRef = useRef<HTMLInputElement>(null);

  const [accountForm, setAccountForm] = useState<AccountFormData>({
    name: "",
    username: "",
    email: "",
    bio: "",
    phone: "",
  });

  const [securityForm, setSecurityForm] = useState<SecurityFormData>({
    currentPassword: "",
    newPassword: "",
    confirmPassword: "",
  });

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

  useEffect(() => {
    const loadUser = async () => {
      try {
        const [user, prefs] = await Promise.all([
          getCurrentUser(),
          getNotificationPreferences(),
        ]);
        setAccountForm({
          name: user.name || "",
          username: user.username || "",
          email: user.email,
          bio: user.bio || "",
          phone: user.phone || "",
        });
        setNotifications(prefs);
        setProfileImage(user.profile_picture || DEFAULT_PROFILE_PICTURE);
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

  const handleNotificationChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const key = e.target.name as keyof NotificationSettings;
    const nextValue = e.target.checked;
    const previousValue = notifications[key];

    setNotificationError("");
    setNotifications((prev) => ({
      ...prev,
      [key]: nextValue,
    }));
    setIsSavingNotifications(true);

    try {
      const updated = await updateNotificationPreferences({
        [key]: nextValue,
      });
      setNotifications(updated);
    } catch (err: any) {
      setNotifications((prev) => ({
        ...prev,
        [key]: previousValue,
      }));
      const detail = err?.response?.data?.detail;
      setNotificationError(
        detail || "Failed to update notification preferences. Please try again."
      );
    } finally {
      setIsSavingNotifications(false);
    }
  };

  const handleSave = async () => {
    setIsSaving(true);
    setErrorMessage("");
    setSuccessMessage("");
    try {
      const updatedUser = await updateProfile({
        name: accountForm.name || undefined,
        username: accountForm.username || undefined,
        phone: accountForm.phone || undefined,
      });

      setAccountForm((prev) => ({
        ...prev,
        name: updatedUser?.name ?? prev.name,
        username: updatedUser?.username ?? prev.username,
        phone: updatedUser?.phone ?? prev.phone,
      }));

      window.dispatchEvent(
        new CustomEvent("userProfileUpdated", {
          detail: {
            name: updatedUser?.name ?? accountForm.name,
            username: updatedUser?.username ?? accountForm.username,
            email: updatedUser?.email ?? accountForm.email,
            phone: updatedUser?.phone ?? accountForm.phone,
            profile_picture: updatedUser?.profile_picture ?? profileImage,
          },
        })
      );

      setSuccessMessage("Profile updated successfully!");
      setTimeout(() => setSuccessMessage(""), 3000);
    } catch (err: any) {
      const detail = err?.response?.data?.detail;
      setErrorMessage(detail || "Failed to save profile. Please try again.");
    } finally {
      setIsSaving(false);
    }
  };

  const handlePasswordSave = async () => {
    setPasswordError("");
    setPasswordSuccess("");
    if (securityForm.newPassword !== securityForm.confirmPassword) {
      setPasswordError("New passwords do not match.");
      return;
    }
    if (!securityForm.currentPassword || !securityForm.newPassword) {
      setPasswordError("Please fill in all password fields.");
      return;
    }
    setIsSavingPassword(true);
    try {
      await changePassword(securityForm.currentPassword, securityForm.newPassword);
      setPasswordSuccess("Password updated successfully!");
      setSecurityForm((prev: SecurityFormData) => ({ ...prev, currentPassword: "", newPassword: "", confirmPassword: "" }));
      setTimeout(() => setPasswordSuccess(""), 3000);
    } catch (err: any) {
      const detail = err?.response?.data?.detail;
      setPasswordError(detail || "Failed to update password. Please try again.");
    } finally {
      setIsSavingPassword(false);
    }
  };

  const handleLogout = async () => {
    await logout();
    navigate('/');

  };

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    if (!file.type.startsWith("image/")) {
      setPictureError("Please select an image file.");
      return;
    }
    if (file.size > 1.5 * 1024 * 1024) {
      setPictureError("Image must be smaller than 1.5 MB.");
      return;
    }

    setPictureError("");
    setPictureUploading(true);

    const reader = new FileReader();
    reader.onload = async (event) => {
      const base64 = event.target?.result as string;
      try {
        await updateProfilePicture(base64);
        setProfileImage(base64);
        window.dispatchEvent(new CustomEvent('profilePictureUpdated', { detail: { picture: base64 } }));
        setSuccessMessage("Profile picture updated!");
        setTimeout(() => setSuccessMessage(""), 3000);
      } catch {
        setPictureError("Failed to upload picture. Please try again.");
      } finally {
        setPictureUploading(false);
        if (fileInputRef.current) fileInputRef.current.value = "";
      }
    };
    reader.readAsDataURL(file);
  };

  const closeDeleteModal = () => {
    setShowDeleteConfirm(false);
    setDeletePassword("");
    setDeleteError("");
  };

  const confirmDeleteAccount = async () => {
    if (!deletePassword) {
      setDeleteError("Please enter your password.");
      return;
    }
    setIsDeleting(true);
    setDeleteError("");
    try {
      await deleteAccount(deletePassword);
      // deleteAccount handles redirect to "/"
    } catch (err: any) {
      setIsDeleting(false);
      const detail = err?.response?.data?.detail;
      setDeleteError(detail === "Incorrect password." ? "Incorrect password." : "Failed to delete account. Please try again.");
    }
  };

  return (
    <div className="settings-container">
      <div className="settings-background-shapes">
        <div className="settings-shape settings-shape-1"></div>
        <div className="settings-shape settings-shape-2"></div>
        <div className="settings-shape settings-shape-3"></div>
      </div>

      {/* Delete Confirmation Modal */}
      {showDeleteConfirm && (
        <div className="modal-overlay">
          <div className="modal-box">
            <h4>Delete Account?</h4>
            <p>
              This will permanently delete your account and all portfolio data.
              This action cannot be undone.
            </p>
            <div className="form-group" style={{ marginBottom: "1rem" }}>
              <label style={{ fontSize: "0.9rem", fontWeight: 600, color: "#374151" }}>
                Enter your password to confirm
              </label>
              <input
                type="password"
                value={deletePassword}
                onChange={(e) => setDeletePassword(e.target.value)}
                placeholder="Your current password"
                disabled={isDeleting}
                onKeyDown={(e) => e.key === "Enter" && confirmDeleteAccount()}
                style={{ marginTop: "0.5rem" }}
              />
            </div>
            {deleteError && (
              <p style={{ color: "#ef4444", fontSize: "0.875rem", marginBottom: "1rem" }}>
                {deleteError}
              </p>
            )}
            <div className="modal-actions">
              <button
                className="modal-cancel-btn"
                onClick={closeDeleteModal}
                disabled={isDeleting}
              >
                Cancel
              </button>
              <button
                className="modal-confirm-btn"
                onClick={confirmDeleteAccount}
                disabled={isDeleting}
              >
                {isDeleting ? "Deleting..." : "Yes, Delete My Account"}
              </button>
            </div>
          </div>
        </div>
      )}

      <div className="settings-content">
        {/* Sidebar Navigation */}
        <div className="settings-sidebar">
          <div className="settings-header">
            <h2>Settings</h2>
            <Link to="/dashboard" className="back-link">
              ← Back to Dashboard
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
              className={`nav-tab ${activeTab === "notifications" ? "active" : ""}`}
              onClick={() => setActiveTab("notifications")}
            >
              <span className="tab-icon">🔔</span>
              Notifications
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
                <p>Update your name, username, and phone number</p>
              </div>
              {errorMessage && (
                <div className="error-banner">{errorMessage}</div>
              )}

              <div className="profile-section">
                <div className="profile-image-container">
                  <input
                    ref={fileInputRef}
                    type="file"
                    accept="image/*"
                    style={{ display: "none" }}
                    onChange={handleFileChange}
                  />
                  <div
                    className="profile-image-wrapper"
                    onClick={() => fileInputRef.current?.click()}
                    title="Click to change profile picture"
                  >
                    <img
                      src={profileImage}
                      alt="Profile"
                      className="profile-image"
                    />
                    <div className="profile-upload-overlay">
                      {pictureUploading ? "⏳" : "📷"}
                    </div>
                  </div>
                  {pictureError && (
                    <p className="picture-error">{pictureError}</p>
                  )}
                  {pictureUploading ? (
                    <p className="picture-uploading">Uploading...</p>
                  ) : (
                    <button
                      className="upload-button"
                      style={{ marginTop: "0.5rem" }}
                      onClick={() => fileInputRef.current?.click()}
                    >
                      Change Photo
                    </button>
                  )}
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
                      name="name"
                      value={accountForm.name}
                      onChange={handleAccountChange}
                      placeholder="Your full name"
                    />
                  </div>
                  <div className="form-group">
                    <label>Username</label>
                    <input
                      type="text"
                      name="username"
                      value={accountForm.username}
                      onChange={handleAccountChange}
                      placeholder="Your username"
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
                      name="phone"
                      value={accountForm.phone}
                      onChange={handleAccountChange}
                      placeholder="Your phone number"
                    />
                  </div>
                </div>
              </div>

              <button
                onClick={handleSave}
                className="save-button"
                disabled={isSaving}
              >
                {isSaving ? (
                  <><span className="spinner"></span> Saving...</>
                ) : (
                  "Save Profile"
                )}
              </button>

              {/* Danger Zone */}
              <div className="danger-zone">
                <h4>Danger Zone</h4>
                <p>
                  Permanently delete your account and all associated portfolio
                  data. This cannot be undone.
                </p>
                
                <button
                  className="delete-account-btn"
                  onClick={() => setShowDeleteConfirm(true)}
                >
                  Delete Account
                </button>
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

              {passwordError && (
                <div className="error-banner">{passwordError}</div>
              )}
              {passwordSuccess && (
                <div className="success-banner">
                  <span className="success-icon">✅</span> {passwordSuccess}
                </div>
              )}

              <button
                onClick={handlePasswordSave}
                className="save-button"
                disabled={isSavingPassword}
              >
                {isSavingPassword ? (
                  <>
                    <span className="spinner"></span> Saving...
                  </>
                ) : (
                  "Update Password"
                )}
              </button>
            </div>
          )}

          {/* Notifications Tab */}
          {activeTab === "notifications" && (
            <div className="tab-content">
              <div className="content-header">
                <h3>Notification Preferences</h3>
                <p>Choose which alerts and updates you want to receive</p>
                {isSavingNotifications && <p>Saving preferences...</p>}
              </div>
              {notificationError && <div className="error-banner">{notificationError}</div>}

              <div className="notifications-list">
                <div className="notification-item">
                  <div className="notification-info">
                    <h4>Email Alerts</h4>
                    <p>Master switch for all email delivery from StockSense</p>
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
                    <h4>Market Alerts</h4>
                    <p>Get notified when tracked stocks hit your target price</p>
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

              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default Settings;
