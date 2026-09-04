import React, { useState } from "react";
import "./App.css";
import { BrowserRouter, Routes, Route, Outlet } from "react-router-dom";
import { Toaster } from "./components/ui/sonner";
import Header from "./components/Header";
import LiveDrop, { LiveDropStrip } from "./components/LiveDrop";
import UpgradePanel from "./components/UpgradePanel";
import SkinsSection from "./components/SkinsSection";
import SettingsModal from "./components/SettingsModal";
import { Logo } from "./components/Logo";
import { useSession, loadSettings, saveSettings } from "./hooks/useSession";
import { AuthProvider } from "./hooks/useAuth";
import { SessionProvider, useSessionCtx } from "./hooks/useSessionCtx";
import TosPage from "./pages/TosPage";
import AuthCallbackPage from "./pages/AuthCallbackPage";
import ProfilePage from "./pages/ProfilePage";
import AdminPage from "./pages/AdminPage";

// Header + live-drop feed shared by every page
const Shell = () => {
  const session = useSession();
  const [topUpOpen, setTopUpOpen] = useState(false);
  return (
    <SessionProvider value={{ ...session, topUpOpen, setTopUpOpen }}>
      <div className="min-h-screen bg-[#0d0e12] text-white">
        <Header stats={session.stats} user={session.user} topUpOpen={topUpOpen} setTopUpOpen={setTopUpOpen} />
        <div className="flex">
          <LiveDrop drops={session.drops} />
          <main className="flex-1 min-w-0">
            <LiveDropStrip drops={session.drops} />
            <div className="px-3 py-4 sm:px-4 sm:py-6">
              <Outlet />
            </div>
          </main>
        </div>
      </div>
    </SessionProvider>
  );
};

const Home = () => {
  const { sessionId, setStats, user, setUser, refreshUser, refreshDrops, setTopUpOpen } = useSessionCtx();
  const [settings, setSettings] = useState(loadSettings);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [target, setTarget] = useState(null);
  const [betSkins, setBetSkins] = useState([]);
  const toggleBetSkin = (sk) => setBetSkins((prev) => (prev[0]?.uid === sk.uid ? [] : [sk]));

  const updateSettings = (s) => {
    setSettings(s);
    saveSettings(s);
  };

  const handleUpgraded = (res) => {
    setUser((u) => ({ ...u, balance: res.balance }));
    setStats((s) => ({ ...s, upgrades: res.upgrades_total }));
    refreshDrops();
    refreshUser();
    setBetSkins([]);
    if (res.win) setTarget(null);
  };

  return (
    <div className="max-w-[980px] mx-auto">
      <div className="flex items-center justify-center gap-2 mb-4 sm:mb-6 fade-up" data-testid="page-title">
        <Logo size={34} className="sm:w-[38px] sm:h-[38px]" />
        <h1 className="text-[24px] sm:text-[30px] font-black uppercase tracking-wide">BLOXGRADE</h1>
      </div>
      <UpgradePanel
        sessionId={sessionId}
        user={user}
        settings={settings}
        onSettingsChange={updateSettings}
        onOpenSettings={() => setSettingsOpen(true)}
        onUpgraded={handleUpgraded}
        target={target}
        onClearTarget={() => setTarget(null)}
        betSkins={betSkins}
        onRemoveBetSkin={(uid) => setBetSkins((prev) => prev.filter((b) => b.uid !== uid))}
      />
      <SkinsSection
        onTopUp={() => setTopUpOpen(true)}
        user={user}
        target={target}
        onSelectTarget={setTarget}
        betSkins={betSkins}
        onToggleBetSkin={toggleBetSkin}
        sound={settings.sound}
      />
      <SettingsModal open={settingsOpen} onOpenChange={setSettingsOpen} settings={settings} onSave={updateSettings} />
    </div>
  );
};

function App() {
  return (
    <div className="App">
      <BrowserRouter>
        <AuthProvider>
          <Routes>
            <Route element={<Shell />}>
              <Route path="/" element={<Home />} />
              <Route path="/tos" element={<TosPage />} />
              <Route path="/profile" element={<ProfilePage />} />
            </Route>
            <Route path="/auth/callback" element={<AuthCallbackPage />} />
            <Route path="/admin" element={<AdminPage />} />
          </Routes>
        </AuthProvider>
      </BrowserRouter>
      <Toaster theme="dark" position="top-center" richColors />
    </div>
  );
}

export default App;
