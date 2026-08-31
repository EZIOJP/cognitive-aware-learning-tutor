import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { autoApplyRoutinesToday } from "../api/plannerClient";
import { loadPlanningPrefs } from "../components/productivity/planningPrefs";
import { resolveApiUrl, resolveVocabApiUrl } from "../utils/resolveBackendUrl";

interface AuthUser {
  id: number;
  username: string;
  display_name?: string | null;
  is_admin?: boolean;
}

interface AuthContextValue {
  token: string | null;
  user: AuthUser | null;
  isAdmin: boolean;
  isAuthenticated: boolean;
  sessionReady: boolean;
  login: (username: string, password: string) => Promise<void>;
  register: (username: string, password: string) => Promise<void>;
  logout: () => void;
  setTokenFromFace: (token: string, user: AuthUser) => void;
  updateProfile: (patch: { display_name: string | null }) => Promise<AuthUser>;
}

const TOKEN_KEY = "vocab:auth-token";

/** Survive Vite HMR: a new createContext() would orphan AuthProvider and crash useAuth. */
const AUTH_CTX_KEY = "__calt_auth_context__";
type AuthCtx = ReturnType<typeof createContext<AuthContextValue | null>>;
const AuthContext: AuthCtx =
  (typeof globalThis !== "undefined" && (globalThis as Record<string, AuthCtx | undefined>)[AUTH_CTX_KEY]) ||
  createContext<AuthContextValue | null>(null);
if (typeof globalThis !== "undefined") {
  (globalThis as Record<string, AuthCtx>)[AUTH_CTX_KEY] = AuthContext;
}

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

function persistSession(token: string, user: AuthUser) {
  localStorage.setItem(TOKEN_KEY, token);
  return { token, user };
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [token, setToken] = useState<string | null>(() => localStorage.getItem(TOKEN_KEY));
  const [user, setUser] = useState<AuthUser | null>(null);
  const [sessionReady, setSessionReady] = useState(false);

  useEffect(() => {
    let cancelled = false;

    const boot = async () => {
      const existing = localStorage.getItem(TOKEN_KEY);
      if (existing) {
        try {
          const u = await apiFetch("/auth/me", { method: "GET" }, existing);
          if (cancelled) return;
          setToken(existing);
          setUser(u);
          setSessionReady(true);
          return;
        } catch {
          localStorage.removeItem(TOKEN_KEY);
        }
      }
      try {
        const data = await apiFetch("/auth/local-session", { method: "GET" });
        if (cancelled) return;
        localStorage.setItem(TOKEN_KEY, data.token);
        setToken(data.token);
        setUser(data.user);
      } catch {
        if (!cancelled) {
          setToken(null);
          setUser(null);
        }
      } finally {
        if (!cancelled) setSessionReady(true);
      }
    };

    void boot();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (!token || !user) return;
    if (!loadPlanningPrefs().autoApplyRoutinesOnLogin) return;
    autoApplyRoutinesToday().catch(() => {
      /* API may be offline at login — routines apply is best-effort */
    });
  }, [token, user?.id]);

  const login = async (username: string, password: string) => {
    const data = await apiFetch("/auth/login", {
      method: "POST",
      body: JSON.stringify({ username, password }),
    });
    const next = persistSession(data.token, data.user);
    setToken(next.token);
    setUser(next.user);
  };

  const register = async (username: string, password: string) => {
    const data = await apiFetch("/auth/register", {
      method: "POST",
      body: JSON.stringify({ username, password }),
    });
    const next = persistSession(data.token, data.user);
    setToken(next.token);
    setUser(next.user);
  };

  const logout = () => {
    localStorage.removeItem(TOKEN_KEY);
    setToken(null);
    setUser(null);
  };

  const setTokenFromFace = (newToken: string, authUser: AuthUser) => {
    const next = persistSession(newToken, authUser);
    setToken(next.token);
    setUser(next.user);
  };

  const updateProfile = async (patch: { display_name: string | null }) => {
    const u = await apiFetch("/auth/me", {
      method: "PATCH",
      body: JSON.stringify(patch),
    }, token ?? undefined);
    setUser(u);
    return u as AuthUser;
  };

  const value = useMemo<AuthContextValue>(
    () => ({
      token,
      user,
      isAdmin: Boolean(user?.is_admin) || user?.username?.toLowerCase() === "admin",
      isAuthenticated: !!token && !!user,
      sessionReady,
      login,
      register,
      logout,
      setTokenFromFace,
      updateProfile,
    }),
    [token, user, sessionReady]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuthOptional(): AuthContextValue | null {
  return useContext(AuthContext);
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
