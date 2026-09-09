"use client";

import { useRouter } from "next/navigation";
import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { api, ApiError } from "@/lib/api";

export interface CurrentUser {
  id: string;
  email: string;
  full_name: string | null;
}

interface AuthContextValue {
  user: CurrentUser | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<{ mfaRequired: boolean; mfaToken?: string }>;
  register: (email: string, password: string, fullName?: string) => Promise<void>;
  logout: () => Promise<void>;
  refreshUser: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue>({
  user: null,
  loading: true,
  login: async () => ({ mfaRequired: false }),
  register: async () => {},
  logout: async () => {},
  refreshUser: async () => {},
});

function saveToken(token: string) {
  window.localStorage.setItem("access_token", token);
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<CurrentUser | null>(null);
  const [loading, setLoading] = useState(true);

  const refreshUser = useCallback(async () => {
    try {
      const me = await api.get<CurrentUser>("/account/me");
      setUser(me);
    } catch {
      setUser(null);
    }
  }, []);

  useEffect(() => {
    void refreshUser().finally(() => setLoading(false));
  }, [refreshUser]);

  const login = useCallback(async (email: string, password: string) => {
    const result = await api.post<{ access_token?: string; mfa_token?: string }>("/auth/login", { email, password });
    if (result.mfa_token) return { mfaRequired: true, mfaToken: result.mfa_token };
    if (result.access_token) saveToken(result.access_token);
    await refreshUser();
    return { mfaRequired: false };
  }, [refreshUser]);

  const register = useCallback(async (email: string, password: string, fullName?: string) => {
    const result = await api.post<{ access_token: string }>("/auth/register", {
      email, password, full_name: fullName || null, accept_terms: true,
    });
    saveToken(result.access_token);
    await refreshUser();
  }, [refreshUser]);

  const logout = useCallback(async () => {
    try {
      await api.post("/auth/logout");
    } catch {
      // Real, honest no-op -- clearing the local token below is what
      // actually matters for this client; a failed server-side
      // revocation call shouldn't block the user from leaving.
    }
    window.localStorage.removeItem("access_token");
    setUser(null);
  }, []);

  const value = useMemo(() => ({ user, loading, login, register, logout, refreshUser }), [user, loading, login, register, logout, refreshUser]);

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  return useContext(AuthContext);
}

/** Real client-side route guard -- redirects to /login when no real
 * session exists once the initial /account/me check settles. */
export function useRequireAuth() {
  const { user, loading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!loading && !user) router.replace("/login");
  }, [loading, user, router]);

  return { user, loading };
}

export { ApiError };
