import React, { createContext, useCallback, useContext, useEffect, useState } from "react";
import { toast } from "sonner";
import { api, getToken, setToken } from "../lib/api";
import AuthModal from "../components/AuthModal";

const AuthContext = createContext(null);

const ERRORS = {
  denied: "Вход через Discord отменён",
  state: "Сессия авторизации устарела, попробуйте ещё раз",
  token: "Discord не подтвердил вход. Попробуйте ещё раз",
  profile: "Не удалось получить профиль Discord",
};

export function AuthProvider({ children }) {
  const [authUser, setAuthUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [authOpen, setAuthOpen] = useState(false);

  const refresh = useCallback(async () => {
    if (!getToken()) {
      setAuthUser(null);
      setLoading(false);
      return null;
    }
    try {
      const u = await api.me();
      setAuthUser(u);
      return u;
    } catch {
      setToken(null);
      setAuthUser(null);
      return null;
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
    const err = new URLSearchParams(window.location.search).get("auth_error");
    if (err) {
      toast.error(ERRORS[err] || "Ошибка авторизации");
      setAuthOpen(true);
      window.history.replaceState({}, "", window.location.pathname);
    }
  }, [refresh]);

  const login = useCallback(
    async (token) => {
      setToken(token);
      return refresh();
    },
    [refresh]
  );

  const logout = useCallback(async () => {
    try {
      await api.logout();
    } catch {
      /* ignore */
    }
    setToken(null);
    setAuthUser(null);
  }, []);

  const openAuth = useCallback(() => setAuthOpen(true), []);

  return (
    <AuthContext.Provider value={{ authUser, setAuthUser, loading, login, logout, refresh, openAuth }}>
      {children}
      <AuthModal open={authOpen} onOpenChange={setAuthOpen} />
    </AuthContext.Provider>
  );
}

export const useAuth = () => useContext(AuthContext);
