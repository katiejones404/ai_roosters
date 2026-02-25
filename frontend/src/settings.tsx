import React, { useEffect, useState, useRef } from "react";
import { getCurrentUser, logout, deleteAccount, updateProfilePicture } from "./utils/auth";
import { Link } from "react-router-dom";
import "./settings.css";

type TabType = "account" | "security";

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
    twoFactorEnabled: false,
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
        const user = await getCurrentUser();
        setAccountForm({
          name: user.name || "",
          username: user.username || "",
          email: user.email,
          bio: user.bio || "",
          phone: user.phone || "",
        });
        if (user.profile_picture) {
          setProfileImage(user.profile_picture);
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
      setTimeout(() => setSuccessMessage(""), 3000);
    }, 1000);
  };

  const handleLogout = () => {
    if (window.confirm("Are you sure you want to logout?")) {
      logout();
    }
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
