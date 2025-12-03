import axios from "axios";

const API_URL = "http://localhost:8000";

// Token management
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

// API calls
export const register = async (
  email: string,
  password: string
): Promise<void> => {
  const response = await axios.post(`${API_URL}/api/auth/register`, {
    email,
    password,
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

export const logout = (): void => {
  removeToken();
  window.location.href = "/login";
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

// Axios interceptor to add token to all requests
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
  }
);
