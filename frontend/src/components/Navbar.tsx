import React, { useEffect, useState, useRef } from "react";
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

const Navbar = () => {
  const location = useLocation();
  const navigate = useNavigate();
  const [user, setUser] = useState<CurrentUser | null>(null);
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [suggestions, setSuggestions] = useState<StockSuggestion[]>([]);
  const [allTickers, setAllTickers] = useState<string[]>([]);
  const [showSuggestions, setShowSuggestions] = useState(false);

  const dropdownRef = useRef<HTMLDivElement>(null);
  const searchRef = useRef<HTMLDivElement>(null);

  // Fetch user + all available tickers on mount
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

    fetchUser();
    fetchTickers();
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

  // Close dropdown/suggestions when clicking outside
  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setDropdownOpen(false);
      }
      if (searchRef.current && !searchRef.current.contains(e.target as Node)) {
        setShowSuggestions(false);
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
          <Link className={isActive("/dashboard")} to="/dashboard">
            Dashboard
          </Link>
          <Link className={isActive("/portfolio")} to="/portfolio">
            Portfolio
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

      {/* Right: User avatar + dropdown */}
      <div className="navbar-right">
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
