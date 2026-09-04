import { useEffect, useState, useCallback, useRef } from "react";
import { api, getSessionId } from "../lib/api";
import { useAuth } from "./useAuth";

const DEFAULT_SETTINGS = {
  multipliers: [2, 4, 8],
  percents: [35, 55, 75],
  sound: false,
  fastSpin: false,
};

export const loadSettings = () => {
  try {
    const raw = localStorage.getItem("bloxgrade_settings");
    return raw ? { ...DEFAULT_SETTINGS, ...JSON.parse(raw) } : DEFAULT_SETTINGS;
  } catch {
    return DEFAULT_SETTINGS;
  }
};

export const saveSettings = (s) => localStorage.setItem("bloxgrade_settings", JSON.stringify(s));
export { DEFAULT_SETTINGS };

export function useSession() {
  const { authUser } = useAuth();
  const sessionId = authUser?.session_id || getSessionId();
  const sessionIdRef = useRef(sessionId);
  sessionIdRef.current = sessionId;
  const [stats, setStats] = useState({ online: 0, upgrades: 0 });
  const [user, setUser] = useState({ balance: 0, nickname: "Player", skins: [] });
  const [drops, setDrops] = useState([]);

  const refreshUser = useCallback(async () => {
    try {
      const u = await api.user(sessionId);
      if (u.session_id === sessionIdRef.current) setUser(u);
    } catch (e) {
      console.error("user fetch failed", e);
    }
  }, [sessionId]);

  const refreshDrops = useCallback(async () => {
    try {
      setDrops(await api.liveDrops(30));
    } catch (e) {
      console.error("drops fetch failed", e);
    }
  }, []);

  useEffect(() => {
    let alive = true;
    const beat = async () => {
      try {
        const s = await api.presence(sessionId);
        if (alive) setStats(s);
      } catch (e) {
        console.error("presence failed", e);
      }
    };
    beat();
    refreshUser();
    refreshDrops();
    const t1 = setInterval(beat, 15000);
    const t2 = setInterval(refreshDrops, 5000);
    return () => {
      alive = false;
      clearInterval(t1);
      clearInterval(t2);
    };
  }, [sessionId, refreshUser, refreshDrops]);

  return { sessionId, stats, setStats, user, setUser, refreshUser, drops, refreshDrops };
}
