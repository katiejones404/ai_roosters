import React, { useEffect, useState } from "react";
import { Navigate, Outlet, useLocation } from "react-router-dom";
import { getCurrentUser, getToken, removeToken } from "./utils/auth";

type AuthState = "checking" | "authorized" | "unauthorized";

const ProtectedRoute: React.FC = () => {
  const [authState, setAuthState] = useState<AuthState>("checking");
  const location = useLocation();

  useEffect(() => {
    let active = true;

    async function validateSession() {
      if (active) {
        setAuthState("checking");
      }

      if (!getToken()) {
        if (active) {
          setAuthState("unauthorized");
        }
        return;
      }

      try {
        await getCurrentUser();
        if (active) {
          setAuthState("authorized");
        }
      } catch {
        removeToken();
        if (active) {
          setAuthState("unauthorized");
        }
      }
    }

    validateSession();

    return () => {
      active = false;
    };
  }, [location.pathname]);

  if (authState === "checking") {
    //return <div className="auth-checking">Checking session...</div>;
    return
  }

  if (authState === "unauthorized") {
    return <Navigate to="/" replace />;
  }

  return <Outlet />;
};

export default ProtectedRoute;
