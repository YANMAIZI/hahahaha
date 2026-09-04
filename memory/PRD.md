# BLOXGRADE — PRD

## Problem statement (original)
Проект-клон upgrader.pro/cis (BLOXGRADE, Roblox-скины): Discord OAuth, TOS, апгрейдер с рулеткой, редкости, депозиты скинами через админа, админ-панель.
**2026-06 (текущая задача):** казино всегда должно быть в плюсе. Банк казино = что реально задепонили минус что вывели (админ подтверждает получение скина и выдаёт RAP). Если банк не может выплатить выигрыш — выигрыш не должен выпасть («кого-то сливает, кому-то выдаёт»). Настройка выдачи (RTP) в админке. Починить промокоды: −20% комиссия должна вычитаться всегда, промо +10% поверх; защита от абуза промо при банке 0.

## Architecture
- FastAPI `/app/backend/server.py` + MongoDB, React (craco) + Tailwind + shadcn.
- Auth: Discord OAuth → JWT (`bloxgrade_token`), admin — сид-фраза (SHA-256 в `ADMIN_SEED_HASHES`) → JWT role=admin.
- Env: `PUBLIC_APP_URL`, `DISCORD_CLIENT_ID/SECRET`, `JWT_SECRET`, `ADMIN_SEED_HASHES`, `CORS_ORIGINS`.
- Bank collections: `bank_state` (running bank), `bank_ledger` (journal), `bank_settings` (rtp_target), `bank_lock` (lease for payout critical section).

## Users
- Гость / игрок (Discord) / админ (сид-фраза, `/admin`).

## Implemented
- 2026-06 batch 1–3: Discord auth, TOS, рулетка, редкости, депозиты (заявка → админ подтверждает), выводы скинов, профиль, админка.
- 2026-06 batch 4 (bank):
  - Deposit confirm: админ вводит **полный RAP**; credited = RAP×0.8×(1+промо), RAP<20 → 400; банк += RAP.
  - Withdrawal done: банк −= цена скина. Ручная корректировка ±, журнал операций.
  - `/api/upgrade`: шанс только на сервере (= ставка/цена, 1%…75%), клиентский chance игнорируется.
  - Защита выплат (всегда вкл.): выигрыш только если банк ≥ балансы+инвентари+на выводе+цена И прогнозный RTP ≤ rtp_target. Иначе forced_loss (roll переносится в проигрышную зону, игроку — обычный проигрыш). Fail-safe: ошибка проверки → отказ. Критическая секция под asyncio.Lock + Mongo-lease.
  - Admin API: GET /api/admin/bank, PUT /api/admin/bank/settings {rtp_target 0.5–1.0}, POST /api/admin/bank/adjust.
  - Admin UI: вкладка «Банк» (BankTab.jsx): дашборд, RTP-ползунок, корректировка, журнал.
  - Tests: `/app/backend/tests/bank_audit.py` (очищает коллекции!), testing agent iteration_4 — 19/19 pass.

## Backlog
- P0: сид-фраза прод-админа уже в .env (bcrypt). Discord OAuth настроен (redirect: PUBLIC_APP_URL/api/auth/discord/callback).

## Update (2026-06, batch 7 — новое пополнение)
- TopUpModal → мастер: шаг 1 (RAP, быстрые суммы, промокод, кнопка «Пополнить <зачислится>»), шаг 2 (профиль-получатель YSrent1 с аватаром `/receivers/ysrent1.png`, инструкция, привязка Roblox обязательна, названия скинов, «Подтвердить»), вкладка «Мои заявки» (отмена, без редактирования, бейдж ожидающих).
- Backend: DepositIn {description, expected_rap≥20, receiver_id}; RECEIVERS список; требуется roblox_nick+link (400); кулдаун 60с (429); POST /api/deposits/{id}/cancel; статус cancelled в админке (вкладка «Отменённые»); заявленный RAP и получатель видны админу, RAP предзаполняется.
- Tests: testing agent iteration_8 — 16/16 + UI ок.

## Update (2026-06, batch 6 — контроль по игроку)
- `player_deny_probability`: плавный случайный троттлинг выигрыша поверх защиты банка: личный RTP (цель 85%), потолок выноса (×2 депозитов, жёстко для крупных скинов), размер скина относительно депозитов (мелкие почти всегда честно), камбэк после 6 проигрышей, «горячая» серия побед, тонкий банк (первых сливать при запуске), новички (первые 5 игр мягче), общий множитель «Жёсткость».
- Admin: PUT /api/admin/bank/settings (rtp_target, personal_rtp, takeout_multiplier, strictness), GET /api/admin/players, forced_by breakdown.
- UI: 4 ползунка в «Банк», вкладка «Игроки» (read-only, без ручной настройки).
- Tests: tests/player_sim.py (12 игроков, казино в плюсе, max take ≈ 0), testing agent iteration_7 — 11/11 + UI ок.

## Update (2026-06, batch 5 — admin hardening)
- Вход в админку: все 10 слов сид-фразы по порядку (вставка целиком авто-заполняет поля). bcrypt-хэш в `ADMIN_SEED_HASH`.
- Brute force: 5 неудач с IP или 20 глобально за 15 мин → 429 на 15 мин (`login_attempts`). Аудит входов в `admin_audit`.
- Admin JWT 4ч с `jti`, хранится в `admin_sessions`, привязан к User-Agent, отзывается logout'ом; новый вход отзывает старые сессии. Подделанные/старые токены без jti → 403.
- Новый сильный `JWT_SECRET`. Tests: testing agent iteration_6 — 25/25 backend, UI ок; logout-баг (гонка с очисткой токена) исправлен.

## Backlog (остаток)
- P1: показать игроку публичную статистику RTP (опционально), уведомления о статусе депозита.
- P2: экспорт журнала банка, фильтры по датам.

## 2026-06 — Inventory value + item actions
- Total inventory value shown in "Мои скины" panel header (main page, top-right of panel) and in profile (balance block + inventory tab bar).
- Profile inventory: removed "Выбрать для продажи" switch; clicking an item reveals two solid-color buttons «Продать · price» (gold) and «Вывести» (light); "Продать всё · total" kept.
- Full production reset performed (bank 0, all players/games/ledger wiped; shop_items kept). Reusable script: `python3 /app/backend/tests/reset_all.py`.
