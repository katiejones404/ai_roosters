/**
 * App.jsx - Main application component with routing
 */
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import LoginForm from "./components/LoginForm";
import RegisterForm from "./components/RegisterForm";
import ProtectedRoute from "./components/ProtectedRoute";

// Import your other pages (you'll create these later with your team)
// For now, let's create simple placeholder components
function Dashboard() {
  return (
    <div className="p-8">
      <h1 className="text-3xl font-bold">Dashboard</h1>
      <p className="mt-4">Welcome to your dashboard! You're logged in.</p>
      <button
        onClick={() => {
          // Import logout function and use it
          import("./utils/auth").then(({ logout }) => {
            logout();
            window.location.href = "/auth/login";
          });
        }}
        className="mt-4 bg-red-500 text-white px-4 py-2 rounded hover:bg-red-600"
      >
        Logout
      </button>
    </div>
  );
}

function NewsPage() {
  return (
    <div className="p-8">
      <h1 className="text-3xl font-bold">News</h1>
      <p className="mt-4">News articles will appear here (Katie's work)</p>
    </div>
  );
}

function StockPage() {
  return (
    <div className="p-8">
      <h1 className="text-3xl font-bold">Stock Details</h1>
      <p className="mt-4">Stock information will appear here (Andrew's work)</p>
    </div>
  );
}

function SettingsPage() {
  return (
    <div className="p-8">
      <h1 className="text-3xl font-bold">Settings</h1>
      <p className="mt-4">User settings will appear here</p>
    </div>
  );
}

function App() {
  return (
    <BrowserRouter>
      <Routes>
        {/* Public routes - anyone can access */}
        <Route path="/auth/login" element={<LoginForm />} />
        <Route path="/auth/register" element={<RegisterForm />} />

        {/* Protected routes - require login */}
        <Route
          path="/dashboard"
          element={
            <ProtectedRoute>
              <Dashboard />
            </ProtectedRoute>
          }
        />

        <Route
          path="/news"
          element={
            <ProtectedRoute>
              <NewsPage />
            </ProtectedRoute>
          }
        />

        <Route
          path="/stocks/:ticker"
          element={
            <ProtectedRoute>
              <StockPage />
            </ProtectedRoute>
          }
        />

        <Route
          path="/settings"
          element={
            <ProtectedRoute>
              <SettingsPage />
            </ProtectedRoute>
          }
        />

        {/* Root path - redirect to dashboard or login */}
        <Route path="/" element={<Navigate to="/dashboard" replace />} />

        {/* 404 - catch all other routes */}
        <Route
          path="*"
          element={
            <div className="min-h-screen flex items-center justify-center">
              <div className="text-center">
                <h1 className="text-4xl font-bold mb-4">404</h1>
                <p className="text-gray-600">Page not found</p>
              </div>
            </div>
          }
        />
      </Routes>
    </BrowserRouter>
  );
}

export default App;
