// src/Layout.tsx
import React from "react";
import { NavLink, Outlet } from "react-router-dom";
import "./app-header.css"; // header styles (shared by dashboard & settings)

export default function Layout() {
  return (
    <>
      <header className="dashboard-header" aria-label="App header">
        <div className="header-inner">
          <div className="header-left">
            <div className="header-logo">
              Stock<span className="logo-highlight">Sense</span>
            </div>

            <input
              className="header-search"
              type="search"
              placeholder="Search tickers..."
              aria-label="Search tickers"
            />
          </div>

          <nav className="header-nav" aria-label="Main navigation">
            <NavLink to="/dashboard" className={({ isActive }) => (isActive ? "nav-btn active" : "nav-btn")}>
              Dashboard
            </NavLink>
            <NavLink to="/settings" className={({ isActive }) => (isActive ? "nav-btn active" : "nav-btn")}>
              Settings
            </NavLink>
                      {/* For later development...
            <NavLink to="/stocks" className={({ isActive }) => (isActive ? "nav-btn active" : "nav-btn")}>
              Stocks
            </NavLink>
            <NavLink to="/news" className={({ isActive }) => (isActive ? "nav-btn active" : "nav-btn")}>
              News
            </NavLink>
            */}
          </nav>
        </div>
      </header>

      <main>
        <Outlet />
      </main>
    </>
  );
}
