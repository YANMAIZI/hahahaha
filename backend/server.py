from fastapi import FastAPI, APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import ReturnDocument
import asyncio
import os
import logging
import random
import secrets
from pathlib import Path
from pydantic import BaseModel, Field
from typing import List, Optional
from urllib.parse import urlencode
import uuid
import hashlib
import hmac
import time
import bcrypt
import httpx
import jwt
from datetime import datetime, timedelta, timezone


ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

APP_URL = os.environ['PUBLIC_APP_URL'].rstrip('/')
DISCORD_CLIENT_ID = os.environ['DISCORD_CLIENT_ID']
DISCORD_CLIENT_SECRET = os.environ['DISCORD_CLIENT_SECRET']
JWT_SECRET = os.environ['JWT_SECRET']
ADMIN_SEED_HASH = os.environ['ADMIN_SEED_HASH'].encode()
ADMIN_SEED_WORDS = 10
ADMIN_TOKEN_HOURS = 4
ADMIN_MAX_FAILS_IP = 5
ADMIN_MAX_FAILS_GLOBAL = 20
ADMIN_LOCK_MINUTES = 15
CORS_ORIGINS = [o.strip() for o in os.environ['CORS_ORIGINS'].split(',') if o.strip()]
DISCORD_REDIRECT_URI = f"{APP_URL}/api/auth/discord/callback"
DISCORD_API = "https://discord.com/api/v10"

app = FastAPI()
api_router = APIRouter(prefix="/api")

ONLINE_WINDOW_SECONDS = 45
MIN_CHANCE = 0.01
MAX_CHANCE = 0.75

RARITIES = [
    {"key": "stock", "label": "Stock", "color": "#b8bcc9"},
    {"key": "blue", "label": "Blue", "color": "#4b9dff"},
    {"key": "purple", "label": "Purple", "color": "#a35cff"},
    {"key": "pink", "label": "Pink", "color": "#ff4fd8"},
    {"key": "red", "label": "Red", "color": "#ff3b3b"},
    {"key": "gold", "label": "Gold", "color": "#ffc634"},
    {"key": "special", "label": "Special", "color": "#ffe27a"},
    {"key": "forbidden", "label": "Forbidden", "color": "#ff7a1a"},
]



IMG = "https://bloxstrike.net/items/bloxstrike-live"
SHOP_ITEMS = [
    {"id": "case-glove-case", "type": "Case", "name": "Glove Case", "price": 43.0, "rarity": "red", "image": f"{IMG}/123594181073716.png"},
    {"id": "case-chrysalis", "type": "Case", "name": "Chrysalis", "price": 44.0, "rarity": "red", "image": f"{IMG}/134467311250667.png"},
    {"id": "case-glove-case-2", "type": "Case", "name": "Glove Case 2", "price": 50.0, "rarity": "red", "image": f"{IMG}/75374128985311.png"},
    {"id": "case-1", "type": "Case", "name": "Case #1", "price": 88.0, "rarity": "red", "image": f"{IMG}/103053431273169.png"},
    {"id": "package-glock-midas", "type": "Package | Glock-18", "name": "Midas", "price": 396.0, "rarity": "red", "image": f"{IMG}/126726654780672.png"},
    {"id": "package-tec9-medal", "type": "Package | Tec-9", "name": "Medal.tv", "price": 832.0, "rarity": "red", "image": f"{IMG}/71231444746781.png"},
    {"id": "awp-bird-hunt", "type": "AWP", "name": "Bird Hunt", "price": 1125.0, "rarity": "red", "image": f"{IMG}/91355488643704.png"},
    {"id": "m4a1s-anodized-red", "type": "M4A1-S", "name": "Anodized Red", "price": 1580.0, "rarity": "red", "image": f"{IMG}/87908365282079.png"},
]


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def as_utc(dt: Optional[datetime]) -> Optional[datetime]:
    return dt.replace(tzinfo=timezone.utc) if dt is not None and dt.tzinfo is None else dt


# ---------- Models ----------
class PresenceIn(BaseModel):
    session_id: str


class StatsOut(BaseModel):
    online: int
    upgrades: int


class UserOut(BaseModel):
    session_id: str
    balance: float
    nickname: str
    skins: List[dict]
    avatar: Optional[str] = None
    discord_id: Optional[str] = None
    promo_code: Optional[str] = None
    promo_bonus: float = 0.0
    roblox_nick: Optional[str] = None
    roblox_link: Optional[str] = None


class RobloxIn(BaseModel):
    roblox_nick: str = Field(min_length=3, max_length=20)
    roblox_link: str = Field(min_length=10, max_length=400)


class PromoIn(BaseModel):
    code: str = Field(min_length=1, max_length=32)


class DepositIn(BaseModel):
    description: str = Field(min_length=3, max_length=300)
    expected_rap: float = Field(ge=20, le=1_000_000)
    receiver_id: str = Field(min_length=1, max_length=32)


class AdminLoginIn(BaseModel):
    phrases: List[str] = Field(min_length=ADMIN_SEED_WORDS, max_length=ADMIN_SEED_WORDS)


class AdminConfirmIn(BaseModel):
    rap: float = Field(gt=0, le=1_000_000)
    note: Optional[str] = Field(default=None, max_length=200)


class BankSettingsIn(BaseModel):
    rtp_target: Optional[float] = Field(default=None, ge=0.5, le=1.0)
    drain_chance: Optional[float] = Field(default=None, ge=0.1, le=0.9)
    max_multiplier: Optional[float] = Field(default=None, ge=1.5, le=10.0)


class BankAdjustIn(BaseModel):
    amount: float = Field(ge=-1_000_000, le=1_000_000)
    note: str = Field(min_length=2, max_length=200)


class UidsIn(BaseModel):
    uids: List[str]


class Drop(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    session_id: str
    nickname: str
    item_name: str
    item_type: str
    item_price: float
    item_image: Optional[str] = None
    item_rarity: Optional[str] = None
    chance: float
    created_at: datetime = Field(default_factory=now_utc)


class UpgradeIn(BaseModel):
    session_id: str
    bet_amount: float = Field(ge=0)
    bet_items: List[dict] = []
    target_item: Optional[dict] = None
    chance: Optional[float] = None


class UpgradeOut(BaseModel):
    id: str
    win: bool
    roll: float
    chance: float
    angle: float
    balance: float
    upgrades_total: int


# ---------- Helpers ----------
def to_user_out(user: dict) -> UserOut:
    return UserOut(
        session_id=user["session_id"],
        balance=float(user.get("balance", 0)),
        nickname=user.get("nickname", "Player"),
        skins=user.get("skins", []),
        avatar=user.get("avatar"),
        discord_id=user.get("discord_id"),
        promo_code=user.get("promo_code"),
        promo_bonus=float(user.get("promo_bonus") or 0),
        roblox_nick=user.get("roblox_nick"),
        roblox_link=user.get("roblox_link"),
    )


async def get_or_create_user(session_id: str) -> dict:
    user = await db.users.find_one({"session_id": session_id}, {"_id": 0})
    if not user:
        user = {
            "session_id": session_id,
            "balance": 0.0,
            "nickname": f"Player_{session_id[:4]}",
            "skins": [],
            "created_at": now_utc(),
        }
        await db.users.insert_one(dict(user))
        user.pop("_id", None)
    skins = user.get("skins", [])
    if any("uid" not in sk for sk in skins):
        for sk in skins:
            sk.setdefault("uid", str(uuid.uuid4()))
        await db.users.update_one({"session_id": session_id}, {"$set": {"skins": skins}})
    return user


async def count_online() -> int:
    threshold = now_utc() - timedelta(seconds=ONLINE_WINDOW_SECONDS)
    return await db.presence.count_documents({"last_seen": {"$gte": threshold}})


async def count_upgrades() -> int:
    return await db.upgrades.count_documents({})


def make_token(session_id: str, role: str = "user", hours: int = 24 * 30, extra: Optional[dict] = None) -> str:
    payload = {"sub": session_id, "role": role, "exp": now_utc() + timedelta(hours=hours), "iat": now_utc(), **(extra or {})}
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")


def decode_token(request: Request) -> Optional[dict]:
    auth = request.headers.get("Authorization", "")
    token = auth[7:] if auth.startswith("Bearer ") else request.cookies.get("bg_token")
    if not token:
        return None
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
    except jwt.PyJWTError:
        return None


def read_token(request: Request) -> Optional[str]:
    data = decode_token(request)
    return data["sub"] if data and data.get("role", "user") == "user" else None


def client_ip(request: Request) -> str:
    return request.headers.get("x-forwarded-for", request.client.host if request.client else "?").split(",")[0].strip()


def ua_hash(request: Request) -> str:
    return hashlib.sha256(request.headers.get("user-agent", "").encode()).hexdigest()[:32]


async def require_admin(request: Request) -> dict:
    data = decode_token(request)
    if not data or data.get("role") != "admin" or data.get("type") != "admin" or not data.get("jti"):
        raise HTTPException(status_code=403, detail="Нет доступа")
    sess = await db.admin_sessions.find_one({"jti": data["jti"], "revoked": False, "expires_at": {"$gt": now_utc()}}, {"_id": 0})
    if not sess or not hmac.compare_digest(sess.get("ua_hash", ""), ua_hash(request)):
        raise HTTPException(status_code=403, detail="Нет доступа")
    await db.admin_sessions.update_one({"jti": data["jti"]}, {"$set": {"last_seen": now_utc()}})
    return sess


async def check_admin_lock(ip: str) -> None:
    now = now_utc()
    for key, limit in ((f"ip:{ip}", ADMIN_MAX_FAILS_IP), ("global", ADMIN_MAX_FAILS_GLOBAL)):
        doc = await db.login_attempts.find_one({"identifier": key})
        if not doc:
            continue
        locked_until, window_start = as_utc(doc.get("locked_until")), as_utc(doc.get("window_start"))
        if locked_until and locked_until > now:
            raise HTTPException(status_code=429, detail="Доступ временно заблокирован. Попробуйте позже")
        if doc.get("fails", 0) >= limit and window_start and now - window_start < timedelta(minutes=ADMIN_LOCK_MINUTES):
            await db.login_attempts.update_one({"identifier": key}, {"$set": {"locked_until": now + timedelta(minutes=ADMIN_LOCK_MINUTES)}})
            raise HTTPException(status_code=429, detail="Доступ временно заблокирован. Попробуйте позже")


async def record_admin_fail(ip: str) -> None:
    now = now_utc()
    for key in (f"ip:{ip}", "global"):
        doc = await db.login_attempts.find_one({"identifier": key})
        window_start = as_utc(doc.get("window_start")) if doc else None
        if not window_start or now - window_start > timedelta(minutes=ADMIN_LOCK_MINUTES):
            await db.login_attempts.update_one({"identifier": key}, {"$set": {"fails": 1, "window_start": now, "locked_until": None}}, upsert=True)
        else:
            await db.login_attempts.update_one({"identifier": key}, {"$inc": {"fails": 1}})


PROMO_CODES = {"SINZUKU": 0.10}
DEPOSIT_FEE = 0.20
MIN_DEPOSIT_RAP = 20
DEPOSIT_COOLDOWN_SECONDS = 60
ROBLOX_FRIEND_URL = "https://www.roblox.com/share?code=114adf7ac7b01243b752faf7c6c71b28&type=Profile&source=ProfileShare&stamp=1788366461111"
RECEIVERS = [
    {"id": "ysrent1", "nickname": "YSrent1", "handle": "@YSrent1", "avatar": "/receivers/ysrent1.png", "friend_url": ROBLOX_FRIEND_URL},
]


async def require_user(request: Request) -> dict:
    session_id = read_token(request)
    user = await db.users.find_one({"session_id": session_id}, {"_id": 0}) if session_id else None
    if not user:
        raise HTTPException(status_code=401, detail="Не авторизован")
    return user


async def take_skins(user: dict, uids: List[str], credit: bool = False) -> List[dict]:
    owned = {sk.get("uid"): sk for sk in user.get("skins", []) if sk.get("uid")}
    if not uids or len(uids) > 200 or len(set(uids)) != len(uids) or any(u not in owned for u in uids):
        raise HTTPException(status_code=400, detail="Выбранных скинов нет в вашем инвентаре")
    taken = []
    for u in uids:
        sk = owned[u]
        update: dict = {"$pull": {"skins": {"uid": u}}}
        if credit:
            update["$inc"] = {"balance": float(sk.get("price") or 0)}
        res = await db.users.update_one({"session_id": user["session_id"], "skins.uid": u}, update)
        if res.matched_count:
            taken.append(sk)
    if not taken:
        raise HTTPException(status_code=400, detail="Скины уже использованы")
    return taken


# ---------- Casino bank ----------
BANK_DEFAULTS = {"rtp_target": 0.90, "drain_chance": 0.45, "max_multiplier": 6.0}
MAX_PROMO_BONUS = 0.5
_upgrade_lock = asyncio.Lock()
FATE_WEIGHTS = [(1.5, 30), (2.0, 25), (3.0, 20), (4.0, 12), (6.0, 8), (8.0, 3), (10.0, 2)]


def draw_fate(prev_cycles: List[dict], settings: dict, bank_headroom: float, base: float) -> tuple:
    """Random 'fate' for a deposit cycle: drain (ends near 0) or a win multiplier. Drawn once, before any bets."""
    drain = float(settings["drain_chance"])
    streak = 0
    for c in prev_cycles:
        if c.get("kind") == "drain":
            streak += 1
        else:
            break
    drain *= 0.7 ** streak
    if prev_cycles and prev_cycles[0].get("kind") == "win" and prev_cycles[0].get("multiplier", 0) >= 3:
        drain = min(0.9, drain * 1.5)
    if bank_headroom < base * 2:
        drain = max(drain, 0.8)
    drain = max(0.05, min(0.95, drain))
    if random.random() < drain:
        return "drain", round(random.uniform(0.2, 0.6), 2), {"drain_chance": round(drain, 3), "streak": streak}
    pool = [(m, w) for m, w in FATE_WEIGHTS if m <= float(settings["max_multiplier"])] or [FATE_WEIGHTS[0]]
    m = random.choices([m for m, _ in pool], weights=[w for _, w in pool])[0]
    return "win", m, {"drain_chance": round(drain, 3), "streak": streak}


async def start_luck_cycle(session_id: str, base: float, deposit_id: Optional[str] = None) -> dict:
    settings = await bank_settings()
    bank = await bank_balance()
    li = await liabilities()
    prev = await db.luck_cycles.find({"session_id": session_id}, {"_id": 0}).sort("started_at", -1).to_list(10)
    base = max(float(base), 20.0)
    kind, mult, meta = draw_fate(prev, settings, bank - li["total"], base)
    cycle = {
        "id": str(uuid.uuid4()), "session_id": session_id, "deposit_id": deposit_id, "kind": kind,
        "multiplier": mult, "base": base, "allowance": round(base * mult, 2), "meta": meta, "started_at": now_utc(),
    }
    await db.luck_cycles.update_many({"session_id": session_id, "active": True}, {"$set": {"active": False}})
    await db.luck_cycles.insert_one({**cycle, "active": True})
    return cycle


async def player_stats(session_id: str) -> dict:
    ups = await db.upgrades.find({"session_id": session_id}, {"_id": 0, "bet_amount": 1, "items_total": 1, "win": 1, "forced_loss": 1, "target_item.price": 1, "created_at": 1}).sort("created_at", -1).to_list(5000)
    cycle = await db.luck_cycles.find_one({"session_id": session_id, "active": True}, {"_id": 0})
    if not cycle:
        u = await db.users.find_one({"session_id": session_id}, {"_id": 0, "balance": 1, "skins.price": 1}) or {}
        holdings = float(u.get("balance") or 0) + sum(float(s.get("price") or 0) for s in u.get("skins", []))
        cycle = await start_luck_cycle(session_id, holdings)
    started = as_utc(cycle["started_at"])
    paid_cycle = sum(float((u.get("target_item") or {}).get("price") or 0) for u in ups if u.get("win") and as_utc(u["created_at"]) >= started)
    wagered = sum(float(u.get("bet_amount") or 0) + float(u.get("items_total") or 0) for u in ups)
    paid = sum(float((u.get("target_item") or {}).get("price") or 0) for u in ups if u.get("win"))
    return {"wagered": wagered, "paid": paid, "games": len(ups), "cycle": cycle, "paid_cycle": paid_cycle}


def player_deny_probability(st: dict, price: float) -> tuple:
    """Within the cycle allowance the roulette is honest; past it the player's luck runs out."""
    c = st["cycle"]
    remaining = float(c["allowance"]) - st["paid_cycle"]
    f = {"kind": c["kind"], "multiplier": c["multiplier"], "allowance": c["allowance"], "paid_cycle": round(st["paid_cycle"], 2)}
    if price <= remaining + 1e-6:
        f["p"] = 0.0
        return 0.0, f
    tiny = price <= float(c["base"]) * 0.15 and st["paid_cycle"] <= float(c["allowance"]) * 1.3
    p = 0.7 if tiny else 1.0
    f["p"] = p
    return p, f


async def bank_settings() -> dict:
    doc = await db.bank_settings.find_one({"id": "main"}, {"_id": 0, "id": 0}) or {}
    return {**BANK_DEFAULTS, **doc}


async def bank_balance() -> float:
    doc = await db.bank_state.find_one({"id": "main"}, {"_id": 0})
    return float((doc or {}).get("bank") or 0)


async def bank_add(kind: str, amount: float, note: Optional[str] = None, ref_id: Optional[str] = None, session_id: Optional[str] = None) -> float:
    state = await db.bank_state.find_one_and_update(
        {"id": "main"}, {"$inc": {"bank": float(amount)}}, upsert=True, return_document=ReturnDocument.AFTER, projection={"_id": 0}
    )
    await db.bank_ledger.insert_one({
        "id": str(uuid.uuid4()), "kind": kind, "amount": float(amount), "bank_after": float(state["bank"]),
        "note": note, "ref_id": ref_id, "session_id": session_id, "created_at": now_utc(),
    })
    return float(state["bank"])


async def _sum(collection, match: dict, expr) -> float:
    docs = await collection.aggregate([{"$match": match}, {"$group": {"_id": None, "s": {"$sum": expr}}}]).to_list(1)
    return float(docs[0]["s"]) if docs else 0.0


async def liabilities() -> dict:
    balances = await _sum(db.users, {}, "$balance")
    inv = await db.users.aggregate([{"$unwind": "$skins"}, {"$group": {"_id": None, "s": {"$sum": "$skins.price"}}}]).to_list(1)
    inventory = float(inv[0]["s"]) if inv else 0.0
    pending = await _sum(db.withdrawals, {"status": "pending"}, "$item.price")
    return {"balances": balances, "inventory": inventory, "pending_withdrawals": pending, "total": balances + inventory + pending}


async def rtp_stats() -> dict:
    wagered = await _sum(db.upgrades, {}, {"$add": [{"$ifNull": ["$bet_amount", 0]}, {"$ifNull": ["$items_total", 0]}]})
    paid = await _sum(db.upgrades, {"win": True}, "$target_item.price")
    return {"wagered": wagered, "paid": paid, "rtp": (paid / wagered) if wagered > 0 else 0.0}


async def payout_allowed(target_price: float, total_bet: float) -> tuple:
    """Fail-safe: any error => payout denied. Casino must stay solvent and within RTP."""
    try:
        settings = await bank_settings()
        bank = await bank_balance()
        li = await liabilities()
        if bank + 1e-9 < li["total"] + target_price:
            return False, "bank", {"bank": bank, "liabilities": li["total"]}
        st = await rtp_stats()
        projected = (st["paid"] + target_price) / (st["wagered"] + total_bet)
        if projected > float(settings["rtp_target"]) + 1e-9:
            return False, "rtp", {"projected_rtp": projected, "rtp_target": settings["rtp_target"]}
        return True, "ok", {"bank": bank, "liabilities": li["total"], "projected_rtp": projected}
    except Exception:
        logger.exception("payout check failed — denying payout")
        return False, "error", {}


def losing_roll(chance: float) -> float:
    r = random.random() * (1 - chance)
    half = 0.5 - chance / 2
    return r + chance if r >= half else r


class bank_lock:
    """Serializes payout decisions: in-process lock + Mongo lease (safe across workers/replicas)."""

    leased = False

    async def __aenter__(self):
        await _upgrade_lock.acquire()
        deadline = time.time() + 8
        try:
            while time.time() < deadline:
                now = now_utc()
                doc = await db.bank_lock.find_one_and_update(
                    {"id": "main", "locked_until": {"$lt": now}},
                    {"$set": {"locked_until": now + timedelta(seconds=5)}},
                )
                if doc:
                    self.leased = True
                    return self
                await asyncio.sleep(0.02)
        except Exception:
            logger.exception("bank lock error")
        logger.error("bank lock not acquired — payout will be denied")
        return self

    async def __aexit__(self, *exc):
        try:
            if self.leased:
                await db.bank_lock.update_one({"id": "main"}, {"$set": {"locked_until": now_utc() - timedelta(seconds=1)}})
        finally:
            _upgrade_lock.release()


# ---------- Routes ----------
@api_router.get("/")
async def root():
    return {"message": "BLOXGRADE API"}


@api_router.get("/rarities")
async def rarities():
    return RARITIES


@api_router.post("/presence", response_model=StatsOut)
async def presence(payload: PresenceIn):
    await db.presence.update_one(
        {"session_id": payload.session_id},
        {"$set": {"last_seen": now_utc()}},
        upsert=True,
    )
    return StatsOut(online=await count_online(), upgrades=await count_upgrades())


@api_router.get("/stats", response_model=StatsOut)
async def stats():
    return StatsOut(online=await count_online(), upgrades=await count_upgrades())


@api_router.get("/user/{session_id}", response_model=UserOut)
async def get_user(session_id: str, request: Request):
    if session_id.startswith("discord_") and read_token(request) != session_id:
        raise HTTPException(status_code=401, detail="Не авторизован")
    if len(session_id) > 64:
        raise HTTPException(status_code=400, detail="Некорректная сессия")
    return to_user_out(await get_or_create_user(session_id))


# ---------- Discord auth ----------
@api_router.get("/auth/discord/login")
async def discord_login():
    state = secrets.token_urlsafe(16)
    await db.oauth_states.insert_one({"state": state, "created_at": now_utc()})
    params = {
        "client_id": DISCORD_CLIENT_ID,
        "redirect_uri": DISCORD_REDIRECT_URI,
        "response_type": "code",
        "scope": "identify",
        "state": state,
        "prompt": "none",
    }
    return RedirectResponse(f"https://discord.com/oauth2/authorize?{urlencode(params)}")


@api_router.get("/auth/discord/callback")
async def discord_callback(code: Optional[str] = None, state: Optional[str] = None, error: Optional[str] = None):
    if error or not code:
        return RedirectResponse(f"{APP_URL}/?auth_error=denied")
    if not state or not await db.oauth_states.find_one_and_delete({"state": state}):
        return RedirectResponse(f"{APP_URL}/?auth_error=state")

    async with httpx.AsyncClient(timeout=15) as http:
        token_res = await http.post(
            f"{DISCORD_API}/oauth2/token",
            data={
                "client_id": DISCORD_CLIENT_ID,
                "client_secret": DISCORD_CLIENT_SECRET,
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": DISCORD_REDIRECT_URI,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        if token_res.status_code != 200:
            logger.error("discord token exchange failed: %s", token_res.text)
            return RedirectResponse(f"{APP_URL}/?auth_error=token")
        access_token = token_res.json()["access_token"]
        me_res = await http.get(f"{DISCORD_API}/users/@me", headers={"Authorization": f"Bearer {access_token}"})
        if me_res.status_code != 200:
            return RedirectResponse(f"{APP_URL}/?auth_error=profile")
        me = me_res.json()

    discord_id = me["id"]
    nickname = me.get("global_name") or me.get("username") or f"User_{discord_id[-4:]}"
    avatar = (
        f"https://cdn.discordapp.com/avatars/{discord_id}/{me['avatar']}.png?size=128"
        if me.get("avatar")
        else f"https://cdn.discordapp.com/embed/avatars/{int(discord_id) % 6}.png"
    )
    session_id = f"discord_{discord_id}"
    await db.users.update_one(
        {"session_id": session_id},
        {
            "$set": {"nickname": nickname, "avatar": avatar, "discord_id": discord_id, "last_login": now_utc()},
            "$setOnInsert": {"balance": 0.0, "skins": [], "created_at": now_utc()},
        },
        upsert=True,
    )
    token = make_token(session_id)
    resp = RedirectResponse(f"{APP_URL}/auth/callback#token={token}")
    resp.set_cookie("bg_token", token, httponly=True, secure=True, samesite="lax", max_age=30 * 24 * 3600, path="/")
    return resp


@api_router.get("/auth/me", response_model=UserOut)
async def auth_me(request: Request):
    session_id = read_token(request)
    if not session_id:
        raise HTTPException(status_code=401, detail="Не авторизован")
    user = await db.users.find_one({"session_id": session_id}, {"_id": 0})
    if not user:
        raise HTTPException(status_code=401, detail="Не авторизован")
    return to_user_out(user)


@api_router.post("/auth/logout")
async def auth_logout():
    return {"ok": True}


@api_router.get("/deposit/info")
async def deposit_info():
    return {"friend_url": ROBLOX_FRIEND_URL, "min_rap": MIN_DEPOSIT_RAP, "fee": DEPOSIT_FEE, "receivers": RECEIVERS, "cooldown": DEPOSIT_COOLDOWN_SECONDS}


@api_router.post("/promo/apply", response_model=UserOut)
async def promo_apply(payload: PromoIn, request: Request):
    user = await require_user(request)
    code = payload.code.strip().upper()
    bonus = PROMO_CODES.get(code)
    if bonus is None:
        raise HTTPException(status_code=400, detail="Промокод не найден")
    await db.users.update_one({"session_id": user["session_id"]}, {"$set": {"promo_code": code, "promo_bonus": bonus}})
    user.update({"promo_code": code, "promo_bonus": bonus})
    return to_user_out(user)


@api_router.post("/profile/roblox", response_model=UserOut)
async def profile_roblox(payload: RobloxIn, request: Request):
    user = await require_user(request)
    nick = payload.roblox_nick.strip()
    link = payload.roblox_link.strip()
    if not link.startswith("https://www.roblox.com/") and not link.startswith("https://roblox.com/"):
        raise HTTPException(status_code=400, detail="Ссылка должна вести на roblox.com")
    await db.users.update_one({"session_id": user["session_id"]}, {"$set": {"roblox_nick": nick, "roblox_link": link}})
    user.update({"roblox_nick": nick, "roblox_link": link})
    return to_user_out(user)


@api_router.get("/profile")
async def profile(request: Request):
    user = await require_user(request)
    sid = user["session_id"]
    upgrades = await db.upgrades.find({"session_id": sid}, {"_id": 0}).sort("created_at", -1).to_list(100)
    best = await db.drops.find({"session_id": sid}, {"_id": 0}).sort("item_price", -1).to_list(1)
    history = await db.item_history.find({"session_id": sid}, {"_id": 0}).sort("created_at", -1).to_list(100)
    withdrawn = [h for h in history if h["kind"] == "withdrawn"]
    return {
        "user": to_user_out(user).model_dump(),
        "stats": {
            "upgrades": len(upgrades),
            "wins": sum(1 for u in upgrades if u.get("win")),
            "withdrawn_count": len(withdrawn),
            "withdrawn_sum": sum(float(h.get("price") or 0) for h in withdrawn),
        },
        "best_drop": best[0] if best else None,
        "item_history": history,
        "games": [
            {
                "id": u["id"],
                "created_at": u["created_at"],
                "bet_amount": u.get("bet_amount", 0),
                "items_total": u.get("items_total", 0),
                "chance": u.get("chance"),
                "win": u.get("win"),
                "target": u.get("target_item"),
            }
            for u in upgrades
        ],
    }


@api_router.post("/skins/sell", response_model=UserOut)
async def skins_sell(payload: UidsIn, request: Request):
    user = await require_user(request)
    skins = await take_skins(user, payload.uids, credit=True)
    await db.item_history.insert_many(
        [{"id": str(uuid.uuid4()), "session_id": user["session_id"], "kind": "sold", "item": sk, "price": float(sk.get("price") or 0), "created_at": now_utc()} for sk in skins]
    )
    fresh = await db.users.find_one({"session_id": user["session_id"]}, {"_id": 0})
    return to_user_out(fresh)


@api_router.post("/skins/withdraw", response_model=UserOut)
async def skins_withdraw(payload: UidsIn, request: Request):
    user = await require_user(request)
    skins = await take_skins(user, payload.uids)
    now = now_utc()
    await db.withdrawals.insert_many(
        [{"id": str(uuid.uuid4()), "session_id": user["session_id"], "item": sk, "status": "pending", "created_at": now} for sk in skins]
    )
    await db.item_history.insert_many(
        [{"id": str(uuid.uuid4()), "session_id": user["session_id"], "kind": "withdrawn", "item": sk, "price": float(sk.get("price") or 0), "created_at": now} for sk in skins]
    )
    fresh = await db.users.find_one({"session_id": user["session_id"]}, {"_id": 0})
    return to_user_out(fresh)


# ---------- Deposits ----------
def deposit_public(d: dict) -> dict:
    return {k: v for k, v in d.items() if k != "_id"}


@api_router.post("/deposits")
async def create_deposit(payload: DepositIn, request: Request):
    user = await require_user(request)
    if not user.get("roblox_nick") or not user.get("roblox_link"):
        raise HTTPException(status_code=400, detail="Сначала привяжите Roblox-профиль (ник и ссылка) в профиле")
    receiver = next((r for r in RECEIVERS if r["id"] == payload.receiver_id), None)
    if not receiver:
        raise HTTPException(status_code=400, detail="Профиль для трейда не найден")
    last = await db.deposits.find_one({"session_id": user["session_id"]}, {"_id": 0, "created_at": 1}, sort=[("created_at", -1)])
    if last and (now_utc() - as_utc(last["created_at"])).total_seconds() < DEPOSIT_COOLDOWN_SECONDS:
        wait = int(DEPOSIT_COOLDOWN_SECONDS - (now_utc() - as_utc(last["created_at"])).total_seconds())
        raise HTTPException(status_code=429, detail=f"Не так быстро: следующую заявку можно отправить через {max(1, wait)} сек")
    pending = await db.deposits.count_documents({"session_id": user["session_id"], "status": "pending"})
    if pending >= 5:
        raise HTTPException(status_code=400, detail="У вас уже 5 заявок в ожидании")
    doc = {
        "id": str(uuid.uuid4()),
        "session_id": user["session_id"],
        "nickname": user.get("nickname"),
        "discord_id": user.get("discord_id"),
        "roblox_nick": user.get("roblox_nick"),
        "roblox_link": user.get("roblox_link"),
        "description": payload.description.strip(),
        "expected_rap": round(payload.expected_rap, 2),
        "receiver_id": receiver["id"],
        "receiver_nick": receiver["nickname"],
        "promo_code": user.get("promo_code"),
        "promo_bonus": float(user.get("promo_bonus") or 0),
        "status": "pending",
        "amount": None,
        "created_at": now_utc(),
        "resolved_at": None,
    }
    await db.deposits.insert_one(dict(doc))
    return doc


@api_router.post("/deposits/{deposit_id}/cancel")
async def cancel_deposit(deposit_id: str, request: Request):
    user = await require_user(request)
    res = await db.deposits.update_one(
        {"id": deposit_id, "session_id": user["session_id"], "status": "pending"},
        {"$set": {"status": "cancelled", "resolved_at": now_utc()}},
    )
    if not res.matched_count:
        raise HTTPException(status_code=404, detail="Заявка не найдена или уже обработана")
    return {"ok": True}


@api_router.get("/deposits/my")
async def my_deposits(request: Request):
    user = await require_user(request)
    docs = await db.deposits.find({"session_id": user["session_id"]}, {"_id": 0}).sort("created_at", -1).to_list(50)
    return docs


# ---------- Admin ----------
@api_router.post("/admin/login")
async def admin_login(payload: AdminLoginIn, request: Request):
    ip = client_ip(request)
    await check_admin_lock(ip)
    words = [p.strip().lower() for p in payload.phrases]
    if any(not w or len(w) > 64 or " " in w for w in words):
        await record_admin_fail(ip)
        raise HTTPException(status_code=403, detail="Неверная сид-фраза")
    ok = await asyncio.to_thread(bcrypt.checkpw, " ".join(words).encode(), ADMIN_SEED_HASH)
    await db.admin_audit.insert_one({"id": str(uuid.uuid4()), "event": "login_ok" if ok else "login_fail", "ip": ip, "ua": ua_hash(request), "created_at": now_utc()})
    if not ok:
        await record_admin_fail(ip)
        raise HTTPException(status_code=403, detail="Неверная сид-фраза")
    await db.login_attempts.delete_one({"identifier": f"ip:{ip}"})
    await db.admin_sessions.update_many({"revoked": False}, {"$set": {"revoked": True}})
    jti = secrets.token_urlsafe(24)
    expires = now_utc() + timedelta(hours=ADMIN_TOKEN_HOURS)
    await db.admin_sessions.insert_one({"jti": jti, "ip": ip, "ua_hash": ua_hash(request), "created_at": now_utc(), "expires_at": expires, "revoked": False})
    return {"token": make_token("admin", role="admin", hours=ADMIN_TOKEN_HOURS, extra={"type": "admin", "jti": jti}), "expires_at": expires}


@api_router.post("/admin/logout")
async def admin_logout(request: Request):
    sess = await require_admin(request)
    await db.admin_sessions.update_one({"jti": sess["jti"]}, {"$set": {"revoked": True}})
    return {"ok": True}


@api_router.get("/admin/session")
async def admin_session(request: Request):
    sess = await require_admin(request)
    return {"ok": True, "expires_at": sess["expires_at"]}


@api_router.get("/admin/deposits")
async def admin_deposits(request: Request, status: str = "pending"):
    await require_admin(request)
    if status not in ("pending", "confirmed", "rejected", "cancelled"):
        raise HTTPException(status_code=400, detail="Неверный статус")
    order = 1 if status == "pending" else -1
    docs = await db.deposits.find({"status": status}, {"_id": 0}).sort("created_at", order).to_list(200)
    return docs


@api_router.post("/admin/deposits/{deposit_id}/confirm")
async def admin_confirm_deposit(deposit_id: str, payload: AdminConfirmIn, request: Request):
    await require_admin(request)
    if payload.rap < MIN_DEPOSIT_RAP:
        raise HTTPException(status_code=400, detail=f"Скины дешевле {MIN_DEPOSIT_RAP} RAP не зачисляются — отклоните заявку")
    rap = round(payload.rap, 2)
    dep = await db.deposits.find_one_and_update(
        {"id": deposit_id, "status": "pending"},
        {"$set": {"status": "confirmed", "rap": rap, "note": payload.note, "resolved_at": now_utc()}},
        projection={"_id": 0},
    )
    if not dep:
        raise HTTPException(status_code=404, detail="Заявка не найдена или уже обработана")
    bonus = min(MAX_PROMO_BONUS, max(0.0, float(dep.get("promo_bonus") or 0)))
    net = rap * (1 - DEPOSIT_FEE)
    credited = round(net * (1 + bonus), 2)
    await db.users.update_one({"session_id": dep["session_id"]}, {"$inc": {"balance": credited}})
    await db.deposits.update_one({"id": deposit_id}, {"$set": {"credited": credited, "amount": credited, "fee": DEPOSIT_FEE, "bonus_applied": bonus}})
    bank = await bank_add("deposit", rap, note=f"{dep.get('nickname')}: +{rap} RAP → {credited}", ref_id=deposit_id, session_id=dep["session_id"])
    await start_luck_cycle(dep["session_id"], credited, deposit_id)
    return {"ok": True, "rap": rap, "credited": credited, "bank": bank}


@api_router.post("/admin/deposits/{deposit_id}/reject")
async def admin_reject_deposit(deposit_id: str, request: Request):
    await require_admin(request)
    res = await db.deposits.update_one({"id": deposit_id, "status": "pending"}, {"$set": {"status": "rejected", "resolved_at": now_utc()}})
    if not res.matched_count:
        raise HTTPException(status_code=404, detail="Заявка не найдена или уже обработана")
    return {"ok": True}


@api_router.get("/admin/withdrawals")
async def admin_withdrawals(request: Request, status: str = "pending"):
    await require_admin(request)
    if status not in ("pending", "done"):
        raise HTTPException(status_code=400, detail="Неверный статус")
    docs = await db.withdrawals.find({"status": status}, {"_id": 0}).sort("created_at", 1 if status == "pending" else -1).to_list(200)
    users = {u["session_id"]: u for u in await db.users.find({"session_id": {"$in": list({d["session_id"] for d in docs})}}, {"_id": 0, "session_id": 1, "nickname": 1, "roblox_nick": 1, "roblox_link": 1, "discord_id": 1}).to_list(500)}
    for d in docs:
        d["user"] = users.get(d["session_id"])
    return docs


@api_router.post("/admin/withdrawals/{withdrawal_id}/done")
async def admin_withdrawal_done(withdrawal_id: str, request: Request):
    await require_admin(request)
    w = await db.withdrawals.find_one_and_update(
        {"id": withdrawal_id, "status": "pending"}, {"$set": {"status": "done", "resolved_at": now_utc()}}, projection={"_id": 0}
    )
    if not w:
        raise HTTPException(status_code=404, detail="Заявка не найдена")
    price = float((w.get("item") or {}).get("price") or 0)
    bank = await bank_add("withdrawal", -price, note=f"Выдан {(w.get('item') or {}).get('name')}", ref_id=withdrawal_id, session_id=w.get("session_id"))
    return {"ok": True, "bank": bank}


@api_router.get("/admin/bank")
async def admin_bank(request: Request):
    await require_admin(request)
    bank = await bank_balance()
    li = await liabilities()
    st = await rtp_stats()
    deposits_total = await _sum(db.bank_ledger, {"kind": "deposit"}, "$amount")
    withdrawals_total = -await _sum(db.bank_ledger, {"kind": "withdrawal"}, "$amount")
    adjustments_total = await _sum(db.bank_ledger, {"kind": "adjust"}, "$amount")
    forced = await db.upgrades.count_documents({"forced_loss": True})
    forced_by = {d["_id"]: d["n"] for d in await db.upgrades.aggregate([{"$match": {"forced_loss": True}}, {"$group": {"_id": "$forced_reason", "n": {"$sum": 1}}}]).to_list(20)}
    wins = await db.upgrades.count_documents({"win": True})
    total = await db.upgrades.count_documents({})
    ledger = await db.bank_ledger.find({}, {"_id": 0}).sort("created_at", -1).to_list(100)
    return {
        "bank": bank,
        "settings": await bank_settings(),
        "liabilities": li,
        "net": bank - li["total"],
        "deposits_total": deposits_total,
        "withdrawals_total": withdrawals_total,
        "adjustments_total": adjustments_total,
        "rtp": st,
        "games": {"total": total, "wins": wins, "forced_losses": forced, "forced_by": forced_by},
        "ledger": ledger,
    }


@api_router.put("/admin/bank/settings")
async def admin_bank_settings(payload: BankSettingsIn, request: Request):
    await require_admin(request)
    changes = {k: v for k, v in payload.model_dump().items() if v is not None}
    if not changes:
        raise HTTPException(status_code=400, detail="Нет изменений")
    await db.bank_settings.update_one({"id": "main"}, {"$set": {**changes, "updated_at": now_utc()}}, upsert=True)
    labels = {"rtp_target": "RTP", "drain_chance": "Шанс слива", "max_multiplier": "Макс. множитель"}
    note = ", ".join(f"{labels[k]} → ×{v}" if k == "max_multiplier" else f"{labels[k]} → {round(v * 100)}%" for k, v in changes.items())
    await db.bank_ledger.insert_one({"id": str(uuid.uuid4()), "kind": "settings", "amount": 0.0, "bank_after": await bank_balance(), "note": note, "created_at": now_utc()})
    return await bank_settings()


@api_router.get("/admin/players")
async def admin_players(request: Request):
    await require_admin(request)
    pipeline = [
        {"$group": {
            "_id": "$session_id",
            "games": {"$sum": 1},
            "wagered": {"$sum": {"$add": [{"$ifNull": ["$bet_amount", 0]}, {"$ifNull": ["$items_total", 0]}]}},
            "paid": {"$sum": {"$cond": ["$win", {"$ifNull": ["$target_item.price", 0]}, 0]}},
            "wins": {"$sum": {"$cond": ["$win", 1, 0]}},
            "forced": {"$sum": {"$cond": [{"$eq": ["$forced_loss", True]}, 1, 0]}},
            "last_game": {"$max": "$created_at"},
        }},
        {"$sort": {"wagered": -1}},
        {"$limit": 200},
    ]
    rows = await db.upgrades.aggregate(pipeline).to_list(200)
    sids = [r["_id"] for r in rows]
    users = {u["session_id"]: u for u in await db.users.find({"session_id": {"$in": sids}}, {"_id": 0, "session_id": 1, "nickname": 1, "balance": 1, "skins.price": 1, "roblox_nick": 1}).to_list(500)}
    deps = {d["_id"]: d for d in await db.deposits.aggregate([{"$match": {"session_id": {"$in": sids}, "status": "confirmed"}}, {"$group": {"_id": "$session_id", "credited": {"$sum": {"$ifNull": ["$credited", 0]}}, "rap": {"$sum": {"$ifNull": ["$rap", 0]}}}}]).to_list(500)}
    withdrawn = {w["_id"]: w["v"] for w in await db.withdrawals.aggregate([{"$match": {"session_id": {"$in": sids}, "status": "done"}}, {"$group": {"_id": "$session_id", "v": {"$sum": {"$ifNull": ["$item.price", 0]}}}}]).to_list(500)}
    cycles = {c["session_id"]: c for c in await db.luck_cycles.find({"session_id": {"$in": sids}, "active": True}, {"_id": 0}).to_list(500)}
    cycle_paid: dict = {}
    for sid, c in cycles.items():
        cycle_paid[sid] = await _sum(db.upgrades, {"session_id": sid, "win": True, "created_at": {"$gte": c["started_at"]}}, "$target_item.price")
    out = []
    for r in rows:
        u = users.get(r["_id"], {})
        inv = sum(float(s.get("price") or 0) for s in u.get("skins", []))
        c = cycles.get(r["_id"])
        out.append({
            "session_id": r["_id"], "nickname": u.get("nickname", "?"), "roblox_nick": u.get("roblox_nick"),
            "cycle": {"kind": c["kind"], "multiplier": c["multiplier"], "allowance": c["allowance"], "paid": cycle_paid.get(r["_id"], 0.0)} if c else None,
            "deposits": float(deps.get(r["_id"], {}).get("credited", 0)), "deposits_rap": float(deps.get(r["_id"], {}).get("rap", 0)),
            "games": r["games"], "wins": r["wins"], "forced": r["forced"], "wagered": float(r["wagered"]), "paid": float(r["paid"]),
            "rtp": (float(r["paid"]) / float(r["wagered"])) if r["wagered"] else 0.0,
            "balance": float(u.get("balance") or 0), "inventory": inv, "withdrawn": float(withdrawn.get(r["_id"], 0)),
            "net": float(u.get("balance") or 0) + inv + float(withdrawn.get(r["_id"], 0)) - float(deps.get(r["_id"], {}).get("credited", 0)),
            "last_game": r["last_game"],
        })
    return out


@api_router.post("/admin/bank/adjust")
async def admin_bank_adjust(payload: BankAdjustIn, request: Request):
    await require_admin(request)
    if abs(payload.amount) < 0.01:
        raise HTTPException(status_code=400, detail="Сумма должна быть не нулевой")
    bank = await bank_add("adjust", payload.amount, note=payload.note.strip())
    return {"ok": True, "bank": bank}


@api_router.get("/live-drops", response_model=List[Drop])
async def live_drops(limit: int = 30):
    limit = max(1, min(limit, 100))
    docs = await db.drops.find({}, {"_id": 0}).sort("created_at", -1).to_list(limit)
    return [Drop(**d) for d in docs]


@api_router.get("/shop")
async def shop(
    sort: str = "price_desc",
    min_price: Optional[float] = None,
    max_price: Optional[float] = None,
    q: Optional[str] = None,
    rarity: Optional[str] = None,
    limit: int = 60,
):
    query: dict = {}
    if min_price is not None or max_price is not None:
        price_q: dict = {}
        if min_price is not None:
            price_q["$gte"] = min_price
        if max_price is not None:
            price_q["$lte"] = max_price
        query["price"] = price_q
    if q:
        query["name"] = {"$regex": q, "$options": "i"}
    if rarity:
        query["rarity"] = rarity
    direction = 1 if sort == "price_asc" else -1
    docs = await db.shop_items.find(query, {"_id": 0}).sort("price", direction).to_list(max(1, min(limit, 200)))
    return {"items": docs, "total": len(docs)}


@api_router.post("/upgrade", response_model=UpgradeOut)
async def upgrade(payload: UpgradeIn, request: Request):
    if read_token(request) != payload.session_id:
        raise HTTPException(status_code=401, detail="Войдите через Discord, чтобы играть")
    user = await get_or_create_user(payload.session_id)
    balance = float(user.get("balance", 0))

    if payload.bet_amount <= 0 and not payload.bet_items:
        raise HTTPException(status_code=400, detail="Выберите скины или баланс для апгрейда")
    if payload.target_item is None or not payload.target_item.get("id"):
        raise HTTPException(status_code=400, detail="Выберите скин для апгрейда")
    shop_item = await db.shop_items.find_one({"id": str(payload.target_item["id"])}, {"_id": 0})
    if not shop_item:
        raise HTTPException(status_code=400, detail="Скин для апгрейда не найден")
    if payload.bet_amount > balance + 1e-9:
        raise HTTPException(status_code=400, detail="Недостаточно баланса")

    owned = {sk.get("uid"): sk for sk in user.get("skins", []) if sk.get("uid")}
    bet_uids = [str(it.get("uid")) for it in payload.bet_items]
    if len(set(bet_uids)) != len(bet_uids) or any(u not in owned for u in bet_uids):
        raise HTTPException(status_code=400, detail="Выбранных скинов нет в вашем инвентаре")
    bet_skins = [owned[u] for u in bet_uids]
    items_total = sum(float(sk.get("price") or 0) for sk in bet_skins)
    total_bet = payload.bet_amount + items_total
    if total_bet <= 0:
        raise HTTPException(status_code=400, detail="Выберите скины или баланс для апгрейда")

    target_price = float(shop_item.get("price") or 0)
    if target_price <= 0:
        raise HTTPException(status_code=400, detail="Скин для апгрейда недоступен")
    if total_bet > target_price * MAX_CHANCE + 1e-6:
        raise HTTPException(status_code=400, detail="Ставка не может превышать 75% стоимости скина")
    # chance is always derived server-side from bet/price; the client value is ignored
    chance = total_bet / target_price
    if chance < MIN_CHANCE - 1e-9:
        raise HTTPException(status_code=400, detail="Минимальный шанс — 1%: увеличьте ставку")
    chance = min(MAX_CHANCE, chance)

    # atomic debit: balance and skins are checked and taken in one update (no double spend)
    debit_filter: dict = {"session_id": payload.session_id, "balance": {"$gte": payload.bet_amount - 1e-9}}
    if bet_uids:
        debit_filter["skins"] = {"$all": [{"$elemMatch": {"uid": u}} for u in bet_uids]}
    user_update: dict = {"$inc": {"balance": -payload.bet_amount}}
    if bet_uids:
        user_update["$pull"] = {"skins": {"uid": {"$in": bet_uids}}}
    debit = await db.users.update_one(debit_filter, user_update)
    if debit.matched_count == 0:
        raise HTTPException(status_code=400, detail="Недостаточно баланса или скин уже использован")
    fresh = await db.users.find_one({"session_id": payload.session_id}, {"_id": 0, "balance": 1})
    new_balance = float(fresh.get("balance", 0))

    upgrade_id = str(uuid.uuid4())
    async with bank_lock() as lock:
        roll = random.random()
        win = abs(roll * 360 - 180) < chance * 180
        forced_loss = False
        forced_reason = None
        protection: dict = {}
        if win:
            allowed, forced_reason, protection = await payout_allowed(target_price, total_bet)
            if not lock.leased:
                allowed, forced_reason = False, "lock"
            if allowed:
                try:
                    st = await player_stats(payload.session_id)
                    p, factors = player_deny_probability(st, target_price)
                    protection["player"] = factors
                    if random.random() < p:
                        allowed, forced_reason = False, "player"
                except Exception:
                    logger.exception("player check failed — denying payout")
                    allowed, forced_reason = False, "error"
            if not allowed:
                win = False
                forced_loss = True
                roll = losing_roll(chance)
        angle = roll * 360 - 180

        await db.upgrades.insert_one({
            "id": upgrade_id,
            "session_id": payload.session_id,
            "bet_amount": payload.bet_amount,
            "bet_items": bet_skins,
            "items_total": items_total,
            "target_item": shop_item,
            "chance": chance,
            "roll": roll,
            "win": win,
            "forced_loss": forced_loss,
            "forced_reason": forced_reason if forced_loss else None,
            "protection": protection,
            "created_at": now_utc(),
        })

        if win:
            target = {**shop_item, "uid": str(uuid.uuid4())}
            drop = Drop(
                session_id=payload.session_id,
                nickname=user.get("nickname", "Player"),
                item_name=str(target.get("name", "Item")),
                item_type=str(target.get("type", "")),
                item_price=float(target.get("price", 0)),
                item_image=target.get("image"),
                item_rarity=target.get("rarity"),
                chance=chance,
            )
            await db.drops.insert_one(drop.model_dump())
            await db.users.update_one(
                {"session_id": payload.session_id},
                {"$push": {"skins": target}},
            )
            await db.item_history.insert_one(
                {"id": str(uuid.uuid4()), "session_id": payload.session_id, "kind": "won", "item": target, "price": float(shop_item.get("price") or 0), "created_at": now_utc()}
            )

    return UpgradeOut(
        id=upgrade_id,
        win=win,
        roll=roll,
        chance=chance,
        angle=angle,
        balance=new_balance,
        upgrades_total=await count_upgrades(),
    )


app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=CORS_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@app.on_event("startup")
async def ensure_indexes():
    await db.presence.create_index("session_id", unique=True)
    await db.presence.create_index("last_seen")
    await db.drops.create_index("created_at")
    await db.users.create_index("session_id", unique=True)
    await db.item_history.create_index([("session_id", 1), ("created_at", -1)])
    await db.deposits.create_index([("status", 1), ("created_at", 1)])
    await db.withdrawals.create_index([("status", 1), ("created_at", 1)])
    await db.bank_ledger.create_index("created_at")
    await db.upgrades.create_index([("win", 1), ("forced_loss", 1)])
    await db.luck_cycles.create_index([("session_id", 1), ("active", 1)])
    await db.oauth_states.create_index("created_at", expireAfterSeconds=600)
    await db.admin_sessions.create_index("jti", unique=True)
    await db.admin_sessions.create_index("expires_at", expireAfterSeconds=0)
    await db.login_attempts.create_index("identifier", unique=True)
    await db.admin_audit.create_index("created_at")
    await db.bank_lock.update_one({"id": "main"}, {"$setOnInsert": {"locked_until": now_utc() - timedelta(seconds=1)}}, upsert=True)
    for item in SHOP_ITEMS:
        await db.shop_items.update_one({"id": item["id"]}, {"$set": item}, upsert=True)
    await db.drops.delete_many({"$or": [{"item_type": "balance"}, {"item_image": None}, {"item_image": ""}]})
    await db.users.update_many({}, {"$pull": {"skins": {"$or": [{"type": "balance"}, {"id": {"$exists": False}}]}}})


@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
