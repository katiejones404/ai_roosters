/*
 * App.tsx
 * Root application component that defines client-side routing and
 * conditionally renders the navigation bar based on the current page.
 */
import {
  BrowserRouter,
  Routes,
  Route,
  Navigate,
  useLocation,
} from "react-router-dom";

import CreateAccount from "./create_account";
import Login from "./login";
import ForgotPassword from "./ForgotPassword";
import ResetPassword from "./ResetPassword";
import Settings from "./settings";
import Dashboard from "./Dashboard";
import Portfolio from "./portfolio";
import NetWorth from "./NetWorth";
import Navbar from "./components/Navbar";
import ProtectedRoute from "./ProtectedRoute";
import StockDetail from "./StockDetail";
import News from "./News";
import Alerts from "./Alerts";
import HomePage from "./HomePage";
import LandingPage from "./LandingPage";

import "./App.css";
import "./index.css";

function App() {
  return (
    <BrowserRouter>
      <AppContent />
    </BrowserRouter>
  );
}

function AppContent() {
  const location = useLocation();

  const hideNavbar =
    location.pathname === "/login" ||
    location.pathname === "/signup" ||
    location.pathname === "/" ||
    location.pathname === "/forgot-password" ||
    location.pathname === "/reset-password";

  return (
    <>
      {!hideNavbar && <Navbar />}

      <Routes>
        <Route path="/" element={<LandingPage />} />
        <Route path="/signup" element={<CreateAccount />} />
        <Route path="/login" element={<Login />} />
        <Route path="/forgot-password" element={<ForgotPassword />} />
        <Route path="/reset-password" element={<ResetPassword />} />

        <Route element={<ProtectedRoute />}>
          <Route path="/home" element={<HomePage />} />
          <Route path="/portfolio" element={<Portfolio />} />
          <Route path="/dashboard" element={<Dashboard />} />
          <Route path="/networth" element={<NetWorth />} />
          <Route path="/settings" element={<Settings />} />
          <Route path="/stock/:ticker" element={<StockDetail />} />
          <Route path="/news" element={<News />} />
          <Route path="/alerts" element={<Alerts />} />
        </Route>

        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </>
  );
}

export default App;
