import axios from "axios";

let base = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

// Remove trailing slash if present (prevents //api/... issues)
if (base.endsWith("/")) {
  base = base.slice(0, -1);
}

const API_URL = base;

export const getToken = (): string | null => {
  return localStorage.getItem("token");
};

export const setToken = (token: string): void => {
  localStorage.setItem("token", token);
};

export const removeToken = (): void => {
  localStorage.removeItem("token");
};

export const isAuthenticated = (): boolean => {
  return !!getToken();
};

export const register = async (
  email: string,
  username: string,
  password: string,
  confirm_password: string, // #5: added confirm_password
): Promise<void> => {
  const response = await axios.post(`${API_URL}/api/auth/register`, {
    email,
    username,
    password,
    confirm_password, // #5: sent to backend for validation
  });
  return response.data;
};

export const login = async (email: string, password: string): Promise<void> => {
  const response = await axios.post(`${API_URL}/api/auth/login`, {
    email,
    password,
  });

  const { access_token } = response.data;
  setToken(access_token);
};

export const logout = async (): Promise<void> => {
  const token = getToken();

  // #6: Tell the backend to blacklist the token before removing it locally
  if (token) {
    try {
      await axios.post(
        `${API_URL}/api/auth/logout`,
        {},
        { headers: { Authorization: `Bearer ${token}` } },
      );
    } catch {
      // If the backend call fails, still log out locally
    }
  }

  removeToken();
  //window.location.href = "/login";
};

export const getCurrentUser = async (): Promise<any> => {
  const token = getToken();
  if (!token) throw new Error("No token found");

  const response = await axios.get(`${API_URL}/api/auth/me`, {
    headers: {
      Authorization: `Bearer ${token}`,
    },
  });

  return response.data;
};

export const deleteAccount = async (password: string): Promise<void> => {
  const token = getToken();
  await axios.delete(`${API_URL}/api/auth/me`, {
    headers: { Authorization: `Bearer ${token}` },
    data: { password },
  });
  removeToken();
  window.location.href = "/";
};

export const updateProfilePicture = async (base64: string): Promise<void> => {
  const token = getToken();
  await axios.put(
    `${API_URL}/api/auth/me/picture`,
    { profile_picture: base64 },
    { headers: { Authorization: `Bearer ${token}` } }
  );
};

export const updateProfile = async (data: {
  name?: string;
  username?: string;
  phone?: string;
}): Promise<any> => {
  const token = getToken();
  const response = await axios.patch(`${API_URL}/api/auth/me`, data, {
    headers: { Authorization: `Bearer ${token}` },
  });
  return response.data;
};

export const changePassword = async (
  currentPassword: string,
  newPassword: string
): Promise<void> => {
  const token = getToken();
  await axios.patch(
    `${API_URL}/api/auth/me/password`,
    { current_password: currentPassword, new_password: newPassword },
    { headers: { Authorization: `Bearer ${token}` } }
  );
};

export interface NotificationPreferences {
  marketAlerts: boolean;
  pushNotifications: boolean;
}

export const getNotificationPreferences = async (): Promise<NotificationPreferences> => {
  const token = getToken();
  const response = await axios.get(`${API_URL}/api/auth/me/notifications`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  return response.data;
};

export const updateNotificationPreferences = async (
  data: Partial<NotificationPreferences>
): Promise<NotificationPreferences> => {
  const token = getToken();
  const response = await axios.patch(`${API_URL}/api/auth/me/notifications`, data, {
    headers: { Authorization: `Bearer ${token}` },
  });
  return response.data;
};

axios.interceptors.request.use(
  (config) => {
    const token = getToken();
    if (token && config.headers) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  },
);

axios.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error?.response?.status === 401) {
      removeToken();

      const path = window.location.pathname;
      const isPublicRoute =
        path === "/" ||
        path === "/login" ||
        path === "/signup" ||
        path === "/forgot-password" ||
        path === "/reset-password";

      if (!isPublicRoute) {
        window.location.href = "/login";
      }
    }

    return Promise.reject(error);
  },
);
