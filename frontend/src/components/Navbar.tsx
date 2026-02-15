import React, { useEffect, useState } from "react";
import { Link, useLocation } from "react-router-dom";
import { getCurrentUser } from "../utils/auth";
import "./Navbar.css";

const Navbar = () => {
  const location = useLocation();
  const [user, setUser] = useState<any>(null);

  useEffect(() => {
    async function fetchUser() {
      const user = await getCurrentUser();
      setUser(user.username);
    }
    fetchUser();
  }, []);

  const isActive = (path: string) =>
    location.pathname === path ? "nav-link active" : "nav-link";

  return (
    <nav className="navbar">
      <div className="navbar-left">
        <Link to="/" className="navbar-brand">
          Stock<span className="brand-highlight">Sense</span>
        </Link>
      </div>

      <div className="navbar-links">
        <Link className={isActive("/dashboard")} to="/dashboard">
          Dashboard
        </Link>
        <Link className={isActive("/portfolio")} to="/portfolio">
          Portfolio
        </Link>
        <Link className={isActive("/settings")} to="/settings">
          Settings
        </Link>
      </div>

      <div className="right">
        {user ? (
          <span className="username">{user.email}</span>
        ) : (
          <Link className={isActive("/logout")} to="/logout">
            Logout
          </Link>
        )}
      </div>
    </nav>
  );
};

export default Navbar;

