import React from "react";
import { Logo } from "./Logo";
import { formatMoney } from "../lib/api";
import { RobuxIcon } from "./Logo";
import { rarityColor } from "../lib/rarity";

const DropCard = ({ d, className = "", style = {} }) => (
  <div className={`drop-card ${className}`} style={style} data-testid="live-drop-item">
    <div className="flex items-center gap-1 text-[9px] text-[#00a2ff] font-bold">
      <Logo size={9} />
      <span>{(d.chance * 100).toFixed(2)}%</span>
    </div>
    <div className="flex items-end justify-between gap-1">
      <div className="min-w-0">
        <div className="text-[10px] font-extrabold uppercase text-white truncate">{d.item_name}</div>
        <div className="text-[8px] text-[#8e91a3] truncate">{d.item_type || d.nickname}</div>
      </div>
      {d.item_image ? (
        <img src={d.item_image} alt={d.item_name} className="w-9 h-9 object-contain" />
      ) : (
        <div className="w-9 h-9 flex items-center justify-center text-[#ffb000]">
          <RobuxIcon size={18} />
        </div>
      )}
    </div>
    <div className="absolute right-1 top-1 text-[8px] text-[#8e91a3] tabular-nums">{formatMoney(d.item_price)}</div>
  </div>
);

// Horizontal strip shown under the header on phones/tablets (sidebar is hidden there)
export function LiveDropStrip({ drops }) {
  if (!drops || drops.length === 0) return null;
  return (
    <div className="lg:hidden border-b border-[#1e2029] bg-[#0f1015]" data-testid="live-drop-strip">
      <div className="px-3 pt-2 flex items-center gap-1 text-[11px] font-bold text-[#ffb000]">
        <Logo size={11} /> Лучший дроп
      </div>
      <div className="flex gap-2 overflow-x-auto px-3 py-2 no-scrollbar">
        {drops.slice(0, 20).map((d) => (
          <DropCard key={d.id} d={d} className="shrink-0 w-[150px] h-[66px] px-2 py-1.5 flex flex-col justify-between" style={{ boxShadow: `inset 0 -3px 0 ${rarityColor(d.item_rarity)}` }} />
        ))}
      </div>
    </div>
  );
}

export default function LiveDrop({ drops }) {
  return (
    <aside
      className="hidden lg:block w-[150px] shrink-0 border-r border-[#1e2029] bg-[#0f1015] h-[calc(100vh-54px)] sticky top-[54px] overflow-y-auto"
      data-testid="live-drop-feed"
    >
      <div className="p-1.5 space-y-1.5">
        {drops.map((d) => (
          <DropCard key={d.id} d={d} className="h-[66px] px-2 py-1.5 flex flex-col justify-between" style={{ boxShadow: `inset 3px 0 0 ${rarityColor(d.item_rarity)}` }} />
        ))}
      </div>
    </aside>
  );
}
