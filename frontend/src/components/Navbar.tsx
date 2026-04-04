import { useEffect, useState, useRef } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import axios from "axios";
import { getCurrentUser, logout } from "../utils/auth";
import { TICKER_NAMES } from "../utils/stockNames";
import "./Navbar.css";

const API_BASE = (import.meta.env.VITE_API_BASE_URL || "http://localhost:8000").replace(/\/+$/, "");

interface CurrentUser {
  email?: string;
  username?: string;
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
}

// Separate component so SVG has its own JSX context
const BellIcon = () => (
  <svg width="18" height="18" viewBox="0 0 24 24" fill="none"
    stroke="currentColor" strokeWidth="2"
    strokeLinecap="round" strokeLinejoin="round">
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

  // Fetch user + all available tickers + triggered alerts on mount
  useEffect(() => {
    async function fetchUser() {
      try {
        const currentUser = await getCurrentUser();
        setUser(currentUser);
      } catch {
        setUser(null);
      }
    }

    async function fetchTickers() {
      try {
        const res = await axios.get<{ ticker: string }[]>(`${API_BASE}/api/stocks`);
        setAllTickers(res.data.map((s) => s.ticker));
      } catch {
        setAllTickers(Object.keys(TICKER_NAMES));
      }
    }

    async function fetchAlerts() {
      try {
        const res = await axios.get<AlertNotification[]>(`${API_BASE}/api/alerts`);
        const triggered = res.data.filter((a) => !a.is_active);
        setNotifications(triggered);
        if (triggered.length > 0) {
          const seen: string[] = JSON.parse(localStorage.getItem("seenAlertIds") || "[]");
          setHasUnread(triggered.some((a) => !seen.includes(a.id)));
        }
      } catch {
        // silently ignore
      }
    }

    fetchUser();
    fetchTickers();
    fetchAlerts();
  }, []);

  // Sync profile picture when updated from Settings
  useEffect(() => {
    const handlePictureUpdate = (e: Event) => {
      const { picture } = (e as CustomEvent<{ picture: string }>).detail;
      setUser((prev: CurrentUser | null) => prev ? { ...prev, profile_picture: picture } : prev);
    };
    window.addEventListener('profilePictureUpdated', handlePictureUpdate);
    return () => window.removeEventListener('profilePictureUpdated', handlePictureUpdate);
  }, []);

  // Close all menus when clicking outside
  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setDropdownOpen(false);
      }
      if (searchRef.current && !searchRef.current.contains(e.target as Node)) {
        setShowSuggestions(false);
      }
      if (bellRef.current && !bellRef.current.contains(e.target as Node)) {
        setBellOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  // Filter suggestions live as user types
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
        (ticker) =>
          ticker.toUpperCase().includes(upper) ||
          (TICKER_NAMES[ticker] || "").toLowerCase().includes(lower)
      )
      .map((ticker) => ({ ticker, name: TICKER_NAMES[ticker] || ticker }));
    setSuggestions(matched);
    setShowSuggestions(true);
  }, [searchQuery, allTickers]);

  const handleSuggestionClick = (ticker: string) => {
    setSearchQuery("");
    setShowSuggestions(false);
    navigate(`/stock/${encodeURIComponent(ticker)}`);
  };

  const handleBellClick = () => {
    const opening = !bellOpen;
    setBellOpen(opening);
    if (opening && hasUnread) {
      // Mark all current notifications as seen
      const ids = notifications.map((a) => a.id);
      localStorage.setItem("seenAlertIds", JSON.stringify(ids));
      setHasUnread(false);
    }
  };

  const handleDeleteNotification = async (id: string) => {
    try {
      await axios.delete(`${API_BASE}/api/alerts/${id}`);
      setNotifications((prev) => prev.filter((a) => a.id !== id));
      // Also remove from seen list so it doesn't linger
      const seen: string[] = JSON.parse(localStorage.getItem("seenAlertIds") || "[]");
      localStorage.setItem("seenAlertIds", JSON.stringify(seen.filter((s) => s !== id)));
    } catch {
      // ignore
    }
  };

  const handleLogout = async () => {
    setDropdownOpen(false);
    await logout();
    navigate('/');
  };

  const isActive = (path: string) =>
    location.pathname === path ? "nav-link active" : "nav-link";
//Random avatars. Can be changed in settings.
  const avatarSrc =
    user?.profile_picture ||
    `https://api.dicebear.com/7.x/avataaars/svg?seed=${user?.username || "default"}`;

  return (
    <nav className="navbar">
      {/* Left: Logo */}
      <div className="navbar-left">
        <Link to="/" className="navbar-brand">
          Stock<span className="brand-highlight">Sense</span>
        </Link>
      </div>

      {/* Center: Nav links + Search */}
      <div className="navbar-center">
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

          <Link className={isActive("/alerts")} to="/alerts">
            Alerts
          </Link>
        </div>

        <div className="nav-search-wrapper" ref={searchRef}>
          <input
            className="nav-search-input"
            type="text"
            placeholder="Search stocks..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            onFocus={() => searchQuery && setShowSuggestions(true)}
          />
          {showSuggestions && suggestions.length > 0 && (
            <div className="search-suggestions">
              {suggestions.map((s) => (
                <div
                  key={s.ticker}
                  className="suggestion-item"
                  onMouseDown={() => handleSuggestionClick(s.ticker)}
                >
                  <span className="suggestion-ticker">{s.ticker}</span>
                  <span className="suggestion-name">{s.name}</span>
                </div>
              ))}
            </div>
          )}
          {showSuggestions && searchQuery && suggestions.length === 0 && (
            <div className="search-suggestions">
              <div className="suggestion-empty">No matching stocks</div>
            </div>
          )}
        </div>
      </div>

      {/* Right: Bell + User avatar + dropdown */}
      <div className="navbar-right">
        {user && (
          <div className="bell-wrapper" ref={bellRef}>
            <button className="bell-btn" onClick={handleBellClick} title="Notifications">
              <BellIcon />
              {hasUnread && <span className="bell-dot" />}
            </button>

            {bellOpen && (
              <div className="bell-dropdown">
                <div className="bell-dropdown-header">Notifications</div>
                {notifications.length === 0 ? (
                  <div className="bell-empty">No notifications yet. Check back later!</div>
                ) : (
                  <div className="bell-list">
                    {notifications.map((a) => (
                      <div key={a.id} className="bell-item">
                        <div className="bell-item-content">
                          <span className="bell-item-ticker">{a.ticker}</span>
                          <span className="bell-item-text">
                            {a.direction === "above" ? "rose above" : "fell below"} ${a.target_price.toFixed(2)}
                          </span>
                        </div>
                        <button
                          className="bell-item-delete"
                          onClick={() => handleDeleteNotification(a.id)}
                          title="Dismiss"
                        >
                          &#x2715;
                        </button>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>
        )}

        {user ? (
          <div className="user-menu" ref={dropdownRef}>
            <button
              className="user-menu-trigger"
              onClick={() => setDropdownOpen((prev) => !prev)}
            >
              <img src={avatarSrc} alt="avatar" className="user-avatar" />
              <span className="username">{user.username || user.email}</span>
              <span className="dropdown-caret">{dropdownOpen ? "▲" : "▼"}</span>
            </button>
            {dropdownOpen && (
              <div className="user-dropdown">
                <Link
                  to="/settings"
                  className="dropdown-item"
                  onClick={() => setDropdownOpen(false)}
                >
                  ⚙️ Settings
                </Link>
                <button className="dropdown-item dropdown-logout" onClick={handleLogout}>
                  🚪 Logout
                </button>
              </div>
            )}
          </div>
        ) : (
          <Link className="nav-link" to="/login">
            Login
          </Link>
        )}
      </div>
    </nav>
  );
};

export default Navbar;
