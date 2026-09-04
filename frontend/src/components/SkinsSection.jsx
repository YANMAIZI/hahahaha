import React, { useEffect, useRef, useState } from "react";
import { TrendingDownIcon } from "./icons/trending-down";
import { TrendingUpIcon } from "./icons/trending-up";
import { Logo, RobuxIcon } from "./Logo";
import AnimButton from "./AnimButton";
import DiscordButton from "./DiscordButton";
import SkinShowcase from "./SkinShowcase";
import { SearchIcon } from "./icons/search";
import { WalletIcon } from "./icons/wallet";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "./ui/select";
import { api, formatMoney, inventoryTotal } from "../lib/api";
import { useAuth } from "../hooks/useAuth";
import { rarityColor, rarityLabel } from "../lib/rarity";
import { playTick } from "../lib/sound";

const EmptySlot = () => <div className="skin-slot" data-testid="empty-skin-slot" />;

export const SkinCard = ({ item, onClick, selected }) => {
  const color = rarityColor(item.rarity);
  return (
    <div
      className={`skin-slot skin-card cursor-pointer ${selected ? "selected" : ""}`}
      style={{ "--rarity": color }}
      onClick={onClick}
      data-testid="shop-skin-card"
      data-rarity={item.rarity || "stock"}
    >
      <div className="absolute top-1.5 left-1.5 right-1.5 flex items-center justify-between text-[10px]">
        <span className="flex items-center gap-0.5 font-bold text-[#ffb000]">
          {formatMoney(item.price)} <RobuxIcon size={9} />
        </span>
        <span className="rarity-dot" title={rarityLabel(item.rarity)} />
      </div>
      {item.image && <img src={item.image} alt={item.name} className="absolute inset-0 m-auto w-3/5 h-3/5 object-contain drop-shadow-[0_6px_10px_rgba(0,0,0,0.6)]" />}
      <div className="absolute inset-x-1 bottom-1.5 text-center">
        <div className="text-[8px] text-[#7d8194] truncate">{item.type}</div>
        <div className="text-[10px] font-bold truncate">{item.name}</div>
      </div>
    </div>
  );
};

const PanelHeader = ({ title, children }) => (
  <div className="min-h-[52px] px-3 py-2 flex flex-wrap items-center gap-2 sm:gap-3">
    <div className="w-8 h-8 rounded-md bg-[#00a2ff] flex items-center justify-center shrink-0">
      <Logo size={16} className="[&_path]:fill-white" />
    </div>
    <span className="font-bold text-[14px] whitespace-nowrap">{title}</span>
    {children}
  </div>
);

const GRID = "grid grid-cols-3 sm:grid-cols-4 lg:grid-cols-5 gap-2";

const MobileTabs = ({ value, onChange }) => (
  <div className="lg:hidden blox-panel p-1 grid grid-cols-2 gap-1" data-testid="mobile-skins-tabs">
    {[
      { key: "mine", label: "Мои скины" },
      { key: "shop", label: "Выберите скин" },
    ].map((t) => (
      <button
        key={t.key}
        type="button"
        onClick={() => onChange(t.key)}
        className={`h-10 rounded-lg text-[13px] font-bold transition-colors ${value === t.key ? "bg-[#00a2ff] text-white shadow-[0_4px_14px_rgba(0,162,255,0.35)]" : "text-[#8e91a3] hover:text-white"}`}
        data-testid={`mobile-tab-${t.key}`}
      >
        {t.label}
      </button>
    ))}
  </div>
);

const PriceInput = ({ value, onChange, placeholder, testId }) => (
  <div className="relative">
    <RobuxIcon size={11} className="absolute left-2 top-1/2 -translate-y-1/2" />
    <input
      value={value}
      onChange={(e) => onChange(e.target.value.replace(/[^\d.]/g, ""))}
      placeholder={placeholder}
      className="h-8 w-[62px] pl-6 pr-2 rounded-md bg-[#0f1015] text-[12px] text-white placeholder:text-[#5f6377] outline-none focus:ring-1 focus:ring-[#00a2ff]"
      data-testid={testId}
    />
  </div>
);

const GuestInventory = ({ onLogin }) => (
  <div className="relative p-2 pt-0" data-testid="guest-inventory">
    <div className="text-center pt-6 pb-4">
      <div className="font-bold text-[18px]" data-testid="guest-title">
        Вы не авторизованы
      </div>
      <div className="text-[12px] text-[#7d8194] mt-1">Войдите для доступа к трейдам</div>
      <DiscordButton className="mt-4" onClick={onLogin} data-testid="inventory-login-button" />
    </div>
    <SkinShowcase size="md" className="mt-2" />
  </div>
);

const UserInventory = ({ skins, onTopUp, selectedUids, onToggle }) => (
  <div className="relative p-2 pt-0" data-testid="user-inventory">
    {skins.length > 0 ? (
      <div className={GRID}>
        {skins.map((s, i) => (
          <SkinCard key={s.uid || `${s.id || s.name}-${i}`} item={s} selected={selectedUids.includes(s.uid)} onClick={() => onToggle(s)} />
        ))}
      </div>
    ) : (
      <>
        <div className={`${GRID} blur-[3px] opacity-50 pointer-events-none select-none`}>
          {Array.from({ length: 15 }).map((_, i) => (
            <EmptySlot key={i} />
          ))}
        </div>
        <div className="absolute inset-0 flex items-center justify-center">
          <div className="bg-[#0d0e12] rounded-xl px-7 py-5 text-center shadow-[0_10px_40px_rgba(0,0,0,0.6)]" data-testid="topup-skins-card">
            <div className="font-bold text-[14px] mb-3">Пополните скины</div>
            <AnimButton
              icon={WalletIcon}
              size={14}
              className="h-9 px-5 rounded-lg border border-[#00a2ff] text-[#00a2ff] font-bold text-[13px] flex items-center gap-2 mx-auto hover:bg-[#00a2ff]/10 transition-colors"
              onClick={onTopUp}
              data-testid="topup-skins-button"
            >
              Пополнить
            </AnimButton>
          </div>
        </div>
      </>
    )}
  </div>
);

export default function SkinsSection({ onTopUp, user, target, onSelectTarget, betSkins = [], onToggleBetSkin, sound }) {
  const { authUser, openAuth } = useAuth();
  const [sort, setSort] = useState("price_desc");
  const [minPrice, setMinPrice] = useState("");
  const [maxPrice, setMaxPrice] = useState("");
  const [query, setQuery] = useState("");
  const [searchOpen, setSearchOpen] = useState(false);
  const [items, setItems] = useState([]);
  const [mobileTab, setMobileTab] = useState("mine");
  const searchRef = useRef(null);

  useEffect(() => {
    let alive = true;
    const params = { sort };
    if (minPrice !== "") params.min_price = Number(minPrice);
    if (maxPrice !== "") params.max_price = Number(maxPrice);
    if (query) params.q = query;
    api
      .shop(params)
      .then((d) => alive && setItems(d.items || []))
      .catch((e) => console.error("shop failed", e));
    return () => {
      alive = false;
    };
  }, [sort, minPrice, maxPrice, query]);

  const openSearch = () => {
    setSearchOpen(true);
    setTimeout(() => searchRef.current?.focus(), 50);
  };
  const closeSearch = () => {
    if (!query) setSearchOpen(false);
  };

  const sorted = [...items].sort((a, b) => (sort === "price_asc" ? a.price - b.price : b.price - a.price));

  return (
    <section className="grid grid-cols-1 lg:grid-cols-2 gap-3 lg:gap-6 mt-4 sm:mt-5 fade-up" data-testid="skins-section">
      <MobileTabs value={mobileTab} onChange={setMobileTab} />
      <div className={`blox-panel overflow-hidden ${mobileTab === "mine" ? "" : "hidden lg:block"}`} data-testid="my-skins-panel">
        <PanelHeader title="Мои скины">
          {authUser && (
            <div className="ml-auto flex items-center gap-2 h-8 px-3 rounded-md bg-[#0f1015]" title="Общая стоимость инвентаря" data-testid="inventory-value-chip">
              <span className="text-[11px] text-[#8e91a3] whitespace-nowrap">Инвентарь · {user?.skins?.length || 0}</span>
              <span className="text-[13px] font-bold text-[#ffb000] tabular-nums flex items-center gap-1" data-testid="inventory-value">
                {formatMoney(inventoryTotal(user?.skins))} <RobuxIcon size={10} />
              </span>
            </div>
          )}
        </PanelHeader>
        {authUser ? (
          <UserInventory
            skins={user?.skins || []}
            onTopUp={onTopUp}
            selectedUids={betSkins.map((b) => b.uid)}
            onToggle={(sk) => {
              playTick(sound);
              onToggleBetSkin(sk);
            }}
          />
        ) : (
          <GuestInventory onLogin={openAuth} />
        )}
      </div>

      <div className={`blox-panel overflow-hidden ${mobileTab === "shop" ? "" : "hidden lg:block"}`} data-testid="shop-panel">
        <PanelHeader title="Выберите скин">
          <div className="w-full sm:w-auto sm:ml-auto flex items-center gap-2 min-w-0">
            <Select value={sort} onValueChange={setSort}>
              <SelectTrigger className="h-8 w-[100px] shrink-0 bg-[#0f1015] border-0 text-[12px] text-white focus:ring-0" data-testid="sort-select">
                <div className="flex items-center gap-1.5">
                  {sort === "price_desc" ? <TrendingDownIcon size={13} className="text-[#7d8194]" /> : <TrendingUpIcon size={13} className="text-[#7d8194]" />}
                  <SelectValue />
                </div>
              </SelectTrigger>
              <SelectContent className="bg-[#1c1d25] border-0 text-white">
                <SelectItem value="price_desc" className="text-[12px] focus:bg-[#262833] focus:text-white">Цена ↓</SelectItem>
                <SelectItem value="price_asc" className="text-[12px] focus:bg-[#262833] focus:text-white">Цена ↑</SelectItem>
              </SelectContent>
            </Select>

            <div
              className={`flex items-center gap-2 overflow-hidden transition-[max-width,opacity] duration-300 ease-out ${searchOpen ? "max-w-0 opacity-0" : "max-w-[140px] opacity-100"}`}
              data-testid="price-filters"
            >
              <PriceInput value={minPrice} onChange={setMinPrice} placeholder="От" testId="min-price-input" />
              <PriceInput value={maxPrice} onChange={setMaxPrice} placeholder="До" testId="max-price-input" />
            </div>

            <div
              className={`h-8 flex items-center rounded-md bg-[#0f1015] transition-[width] duration-300 ease-out overflow-hidden ${searchOpen ? "w-[172px]" : "w-8"}`}
              data-testid="search-box"
            >
              <AnimButton
                icon={SearchIcon}
                size={14}
                className="w-8 h-8 shrink-0 flex items-center justify-center text-[#7d8194] hover:text-white transition-colors"
                onClick={openSearch}
                data-testid="search-toggle"
              />
              <input
                ref={searchRef}
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                onBlur={closeSearch}
                placeholder="Поиск скина"
                className={`h-8 bg-transparent text-[12px] text-white placeholder:text-[#5f6377] outline-none pr-2 transition-opacity duration-200 ${searchOpen ? "w-full opacity-100" : "w-0 opacity-0"}`}
                data-testid="search-input"
              />
            </div>
          </div>
        </PanelHeader>
        <div className={`p-2 pt-0 ${GRID}`} data-testid="shop-grid">
          {sorted.length > 0
            ? sorted.map((it) => (
                <SkinCard
                  key={it.id || it.name}
                  item={it}
                  selected={target?.id === it.id}
                  onClick={() => {
                    playTick(sound);
                    onSelectTarget(target?.id === it.id ? null : it);
                  }}
                />
              ))
            : Array.from({ length: 20 }).map((_, i) => <EmptySlot key={i} />)}
        </div>
      </div>
    </section>
  );
}
