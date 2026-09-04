import React, { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import { RobuxIcon } from "../Logo";
import { adminApi, formatMoney } from "../../lib/api";

const pct = (v) => `${Math.round(Number(v) * 100)}%`;
const fmtDate = (d) => (d ? new Date(d).toLocaleString("ru-RU", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" }) : "—");

const Money = ({ v, tone = "" }) => (
  <span className={`inline-flex items-center gap-1 font-bold ${tone}`}>{formatMoney(v)} <RobuxIcon size={9} /></span>
);

export default function PlayersTab() {
  const [rows, setRows] = useState(null);
  const load = useCallback(() => adminApi.players().then(setRows).catch(() => toast.error("Не удалось загрузить игроков")), []);
  useEffect(() => {
    load();
    const t = setInterval(load, 20000);
    return () => clearInterval(t);
  }, [load]);

  if (!rows) return <div className="blox-panel h-[160px] flex items-center justify-center text-[13px] text-[#5f6377]" data-testid="players-loading">Загрузка…</div>;

  return (
    <div className="space-y-3" data-testid="players-tab">
      <div className="rounded-lg bg-[#00a2ff]/10 border border-[#00a2ff]/40 px-3 py-2.5 text-[12px] text-[#b4d9ff] leading-snug" data-testid="players-hint">
        При каждом подтверждённом депозите игроку случайно выпадает «судьба»: <b>слив</b> (уйдёт почти в 0) или <b>множитель</b> ×1.5…×10 — столько он максимум сможет выиграть с этого депозита. Пока лимит не исчерпан, рулетка полностью честная; после — везение заканчивается. Сливы подряд снижают шанс следующего слива, крупный выигрыш — повышает. Настраивать вручную ничего не нужно.
      </div>
      {rows.length === 0 && <div className="blox-panel h-[160px] flex items-center justify-center text-[13px] text-[#5f6377]" data-testid="players-empty">Игр пока не было</div>}
      {rows.length > 0 && (
        <div className="blox-panel overflow-x-auto" data-testid="players-table">
          <table className="w-full text-[12px]">
            <thead className="text-[10px] uppercase tracking-wider text-[#7d8194]">
              <tr className="text-left">
                <th className="px-3 py-2">Игрок</th>
                <th className="px-3 py-2">Депозиты</th>
                <th className="px-3 py-2">Поставил</th>
                <th className="px-3 py-2">Выиграл</th>
                <th className="px-3 py-2">Личный RTP</th>
                <th className="px-3 py-2">Судьба депозита</th>
                <th className="px-3 py-2">Игр / побед / сливов</th>
                <th className="px-3 py-2">На руках</th>
                <th className="px-3 py-2">Вывел</th>
                <th className="px-3 py-2">Итог игрока</th>
                <th className="px-3 py-2">Последняя игра</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.session_id} className="border-t border-[#15161b] hover:bg-[#0f1015]" data-testid="players-row">
                  <td className="px-3 py-2">
                    <div className="font-bold truncate max-w-[160px]">{r.nickname}</div>
                    {r.roblox_nick && <div className="text-[10px] text-[#7d8194]">Roblox: {r.roblox_nick}</div>}
                  </td>
                  <td className="px-3 py-2"><Money v={r.deposits} /></td>
                  <td className="px-3 py-2"><Money v={r.wagered} /></td>
                  <td className="px-3 py-2"><Money v={r.paid} /></td>
                  <td className={`px-3 py-2 font-black ${r.rtp > 1 ? "text-[#ff8a8a]" : "text-[#2ecc71]"}`} data-testid="players-rtp">{pct(r.rtp)}</td>
                  <td className="px-3 py-2" data-testid="players-cycle">
                    {r.cycle ? (
                      <div>
                        <span className={`font-black ${r.cycle.kind === "drain" ? "text-[#ff8a8a]" : "text-[#ffb000]"}`}>{r.cycle.kind === "drain" ? "слив" : `×${r.cycle.multiplier}`}</span>
                        <span className="text-[#8e91a3]"> · выдано {formatMoney(r.cycle.paid)} / {formatMoney(r.cycle.allowance)}</span>
                      </div>
                    ) : <span className="text-[#5f6377]">—</span>}
                  </td>
                  <td className="px-3 py-2 text-[#b4b7c7]">{r.games} / {r.wins} / <span className="text-[#ff8a8a]">{r.forced}</span></td>
                  <td className="px-3 py-2"><Money v={r.balance + r.inventory} /></td>
                  <td className="px-3 py-2"><Money v={r.withdrawn} /></td>
                  <td className="px-3 py-2"><Money v={r.net} tone={r.net > 0 ? "text-[#ff8a8a]" : "text-[#2ecc71]"} /></td>
                  <td className="px-3 py-2 text-[#5f6377]">{fmtDate(r.last_game)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <div className="text-[11px] text-[#5f6377]">«Итог игрока» = на руках + вывел − депозиты. Зелёный — казино в плюсе по этому игроку, красный — игрок в плюсе.</div>
    </div>
  );
}
