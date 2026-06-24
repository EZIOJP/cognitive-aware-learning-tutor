import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { resolveApiUrl, resolveVocabApiUrl } from "../utils/resolveBackendUrl";

interface AuthUser {
  id: number;
  username: string;
}

interface AuthContextValue {
  token: string | null;
  user: AuthUser | null;
  isAdmin: boolean;
  isAuthenticated: boolean;
  login: (username: string, password: string) => Promise<void>;
  register: (username: string, password: string) => Promise<void>;
  logout: () => void;
  setTokenFromFace: (token: string, user: AuthUser) => void;
}

const TOKEN_KEY = "vocab:auth-token";

const AuthContext = createContext<AuthContextValue | null>(null);

async function apiFetch(path: string, init?: RequestInit, token?: string) {
  const headers = new Headers(init?.headers || {});
  headers.set("Content-Type", "application/json");
  if (token) headers.set("Authorization", `Bearer ${token}`);
  let res: Response;
  try {
    res = await fetch(`${resolveVocabApiUrl()}${path}`, { ...init, headers });
  } catch {
    throw new Error(
      `Cannot reach backend. Start FastAPI on ${resolveApiUrl()} first (or allow firewall ports 8000/5173 for WiFi).`
    );
  }
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    throw new Error(data.detail || data.error || `HTTP ${res.status}`);
  }
  return data;
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [token, setToken] = useState<string | null>(() => localStorage.getItem(TOKEN_KEY));
  const [user, setUser] = useState<AuthUser | null>(null);

  useEffect(() => {
    if (!token) {
      setUser(null);
      return;
    }
    apiFetch("/auth/me", { method: "GET" }, token)
      .then((u) => setUser(u))
      .catch(() => {
        localStorage.removeItem(TOKEN_KEY);
        setToken(null);
        setUser(null);
      });
  }, [token]);

  const login = async (username: string, password: string) => {
    const data = await apiFetch("/auth/login", {
      method: "POST",
      body: JSON.stringify({ username, password }),
    });
    localStorage.setItem(TOKEN_KEY, data.token);
    setToken(data.token);
    setUser(data.user);
  };

  const register = async (username: string, password: string) => {
    const data = await apiFetch("/auth/register", {
      method: "POST",
      body: JSON.stringify({ username, password }),
    });
    localStorage.setItem(TOKEN_KEY, data.token);
    setToken(data.token);
    setUser(data.user);
  };

  const logout = () => {
    localStorage.removeItem(TOKEN_KEY);
    setToken(null);
    setUser(null);
  };

  const setTokenFromFace = (newToken: string, authUser: AuthUser) => {
    localStorage.setItem(TOKEN_KEY, newToken);
    setToken(newToken);
    setUser(authUser);
  };

  const value = useMemo<AuthContextValue>(
    () => ({
      token,
      user,
      isAdmin: user?.username?.toLowerCase() === "admin",
      isAuthenticated: !!token && !!user,
      login,
      register,
      logout,
      setTokenFromFace,
    }),
    [token, user]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}

