import { useEffect, useState, useRef } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import axios from "axios";
import { getCurrentUser, logout } from "../utils/auth";
import { TICKER_NAMES } from "../utils/stockNames";
import "./Navbar.css";

const API_BASE = (
  import.meta.env.VITE_API_BASE_URL || "http://localhost:8000"
).replace(/\/+$/, "");
const DEFAULT_PROFILE_PICTURE = "/default_pfp.jpg";

const normalizeProfilePicture = (profilePicture?: string): string => {
  const value = (profilePicture || "").trim();
  if (!value) return DEFAULT_PROFILE_PICTURE;
  const lowered = value.toLowerCase();
  if (
    lowered.endsWith("default_pfp.jgp") ||
    lowered.endsWith("default_pfp.jpeg")
  ) {
    return DEFAULT_PROFILE_PICTURE;
  }
  return value;
};

interface CurrentUser {
  username?: string;
  email?: string;
  profile_picture?: string;
}

interface StockSuggestion {
  ticker: string;
  name: string;
}

interface AlertNotification {
  id: string;
  ticker: string;
  target_price: number;
  direction: string;
  is_active: boolean;
  triggered_price?: number | null;
}

const BellIcon = () => (
  <svg
    width="20"
    height="20"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth="2"
    strokeLinecap="round"
    strokeLinejoin="round"
  >
    <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9" />
    <path d="M13.73 21a2 2 0 0 1-3.46 0" />
  </svg>
);

const Navbar = () => {
  const location = useLocation();
  const navigate = useNavigate();

  const [user, setUser] = useState<CurrentUser | null>(null);
  const [dropdownOpen, setDropdownOpen] = useState(false);

  const [searchQuery, setSearchQuery] = useState("");
  const [suggestions, setSuggestions] = useState<StockSuggestion[]>([]);
  const [allTickers, setAllTickers] = useState<string[]>([]);
  const [showSuggestions, setShowSuggestions] = useState(false);

  const [bellOpen, setBellOpen] = useState(false);
  const [hasUnread, setHasUnread] = useState(false);
  const [notifications, setNotifications] = useState<AlertNotification[]>([]);

  const dropdownRef = useRef<HTMLDivElement>(null);
  const searchRef = useRef<HTMLDivElement>(null);
  const bellRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    async function fetchData() {
      try {
        const currentUser = await getCurrentUser();
        setUser(currentUser);

        const tickerRes = await axios.get(`${API_BASE}/api/stocks`);
        setAllTickers(tickerRes.data.map((s: any) => s.ticker));

        const alertRes = await axios.get<AlertNotification[]>(
          `${API_BASE}/api/alerts`,
        );
        const triggered = alertRes.data.filter((a) => !a.is_active);
        setNotifications(triggered);

        if (triggered.length > 0) {
          const seen: string[] = JSON.parse(
            localStorage.getItem("seenAlertIds") || "[]",
          );
          setHasUnread(triggered.some((a) => !seen.includes(a.id)));
        }
      } catch {
        setAllTickers(Object.keys(TICKER_NAMES));
      }
    }

    fetchData();
  }, []);

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (
        dropdownRef.current &&
        !dropdownRef.current.contains(e.target as Node)
      )
        setDropdownOpen(false);
      if (searchRef.current && !searchRef.current.contains(e.target as Node))
        setShowSuggestions(false);
      if (bellRef.current && !bellRef.current.contains(e.target as Node))
        setBellOpen(false);
    }

    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  useEffect(() => {
    const q = searchQuery.trim();

    if (!q) {
      setSuggestions([]);
      setShowSuggestions(false);
      return;
    }

    const upper = q.toUpperCase();
    const lower = q.toLowerCase();

    const matched = allTickers
      .filter(
        (t) =>
          t.toUpperCase().includes(upper) ||
          (TICKER_NAMES[t] || "").toLowerCase().includes(lower),
      )
      .slice(0, 8)
      .map((t) => ({ ticker: t, name: TICKER_NAMES[t] || t }));

    setSuggestions(matched);
    setShowSuggestions(true);
  }, [searchQuery, allTickers]);

  const handleSuggestionClick = (ticker: string) => {
    setSearchQuery("");
    setShowSuggestions(false);
    navigate(`/stock/${encodeURIComponent(ticker)}`);
  };

  const handleLogout = async () => {
    setDropdownOpen(false);
    await logout();
    navigate("/login", { replace: true });
  };

  const markNotificationSeen = (id: string) => {
    const seen: string[] = JSON.parse(localStorage.getItem("seenAlertIds") || "[]");
    if (!seen.includes(id)) {
      const updated = [...seen, id];
      localStorage.setItem("seenAlertIds", JSON.stringify(updated));
    }
    setHasUnread(notifications.some((n) => n.id !== id && !seen.includes(n.id)));
  };

  const handleNotificationClick = (alert: AlertNotification) => {
    markNotificationSeen(alert.id);
    setBellOpen(false);
    navigate(`/stock/${encodeURIComponent(alert.ticker)}`);
  };

  const isActive = (path: string) =>
    location.pathname === path ? "nav-link active" : "nav-link";

  const displayName = user?.username || user?.email || "Account";

  return (
    <nav className="navbar">
      <div className="navbar-container">
        <div className="navbar-left-group">
          <div className="navbar-brand" aria-label="StockSense">
            Stock<span className="brand-highlight">Sense</span>
          </div>

          <div className="navbar-links">
            <Link className={isActive("/home")} to="/home">
              Home
            </Link>
            <Link className={isActive("/dashboard")} to="/dashboard">
              Dashboard
            </Link>
            <Link className={isActive("/portfolio")} to="/portfolio">
              Portfolio
            </Link>
            <Link className={isActive("/networth")} to="/networth">
              Net Worth
            </Link>
            <Link className={isActive("/news")} to="/news">
              News
            </Link>
            <Link className={isActive("/stock-comparison")} to="/stock-comparison">
              Compare
            </Link>
            <Link className={isActive("/alerts")} to="/alerts">
              Alerts
            </Link>
          </div>
        </div>

        <div className="navbar-right-group">
          <div className="nav-search-wrapper" ref={searchRef}>
            <input
              className="nav-search-input"
              type="text"
              placeholder="Search stocks..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              onFocus={() => searchQuery && setShowSuggestions(true)}
            />
            {showSuggestions && (
              <div className="search-suggestions">
                {suggestions.length > 0 ? (
                  suggestions.map((s) => (
                    <div
                      key={s.ticker}
                      className="suggestion-item"
                      onMouseDown={() => handleSuggestionClick(s.ticker)}
                    >
                      <span className="suggestion-ticker">{s.ticker}</span>
                      <span className="suggestion-name">{s.name}</span>
                    </div>
                  ))
                ) : (
                  <div className="suggestion-empty">No matching stocks</div>
                )}
              </div>
            )}
          </div>

          {user && (
            <div className="bell-wrapper" ref={bellRef}>
              <button
                className="bell-btn"
                onClick={() => setBellOpen(!bellOpen)}
                aria-label="Notifications"
                type="button"
              >
                <BellIcon />
                {hasUnread && <span className="bell-dot" />}
              </button>

              {bellOpen && (
                <div className="bell-dropdown">
                  <div className="bell-dropdown-header">Notifications</div>
                  <div className="bell-list">
                    {notifications.length === 0 ? (
                      <div className="bell-empty">No notifications</div>
                    ) : (
                      notifications.map((a) => (
                        <button
                          key={a.id}
                          type="button"
                          className="bell-item"
                          onClick={() => handleNotificationClick(a)}
                          title={`Open ${a.ticker} stock page`}
                        >
                          <span className="bell-item-ticker">{a.ticker}</span>
                          <span className="bell-item-text">
                            Triggered at ${
                              typeof a.triggered_price === "number"
                                ? a.triggered_price.toFixed(2)
                                : a.target_price.toFixed(2)
                            }
                          </span>
                        </button>
                      ))
                    )}
                  </div>
                </div>
              )}
            </div>
          )}

          {user ? (
            <div className="user-menu" ref={dropdownRef}>
              <button
                className="user-menu-trigger"
                onClick={() => setDropdownOpen(!dropdownOpen)}
                type="button"
                aria-label="User menu"
              >
                <img
                  src={normalizeProfilePicture(user.profile_picture)}
                  alt="avatar"
                  className="user-avatar"
                  onError={(e) => {
                    e.currentTarget.src = DEFAULT_PROFILE_PICTURE;
                  }}
                />
                <span className="username" title={displayName}>
                  {displayName}
                </span>
                <span className="dropdown-caret">
                  {dropdownOpen ? "▲" : "▼"}
                </span>
              </button>

              {dropdownOpen && (
                <div className="user-dropdown">
                  <Link
                    to="/settings"
                    className="dropdown-item"
                    onClick={() => setDropdownOpen(false)}
                  >
                    <span className="dropdown-icon">⚙️</span>
                    <span className="dropdown-label">Settings</span>
                  </Link>

                  <button
                    className="dropdown-item dropdown-logout"
                    onClick={handleLogout}
                    type="button"
                  >
                    <span className="dropdown-icon">🚪</span>
                    <span className="dropdown-label">Logout</span>
                  </button>
                </div>
              )}
            </div>
          ) : (
            <Link className="nav-link login-link" to="/login">
              Login
            </Link>
          )}
        </div>
      </div>
    </nav>
  );
};

export default Navbar;
