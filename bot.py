import io
import os
import re
import time
import json
import logging
import hashlib
import asyncio
from datetime import datetime
from io import BytesIO

import aiohttp
import asyncpg
import pandas as pd
import phonenumbers
import pycountry
from aiohttp import web
from bs4 import BeautifulSoup
from phonenumbers import region_code_for_number, country_code_for_region

from telegram import (
    Update,
    BotCommand,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    InputFile,
    ReplyKeyboardRemove,
    CopyTextButton,
)
from telegram.constants import ParseMode
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ContextTypes,
)

# ══════════════════════════════════════════════════════════════
#                      CONFIGURATION
# ══════════════════════════════════════════════════════════════

BOT_TOKEN        = os.environ.get("BOT_TOKEN", "8955797111:AAE45eh3EQUBc-yGogFOi5XxhQ0DLxvW66Y")
BOT_NAME         = os.environ.get("BOT_NAME", "IMS BOT")
BOT_LINK         = os.environ.get("BOT_LINK", "https://t.me/test_bsaad_bot")
NUMBER_LINK      = os.environ.get("NUMBER_LINK", "https://t.me/traffic_zone_main_bot")
METHODS_LINK     = os.environ.get("METHODS_LINK", "https://t.me/traffic_zone_methods")
BASE_ADMIN_IDS   = [int(x.strip()) for x in os.environ.get("ADMIN_IDS", "8856515282,8816769284").split(",")]

# ── Panel 1: EMO SMS ──
PANEL1_BASE      = os.environ.get("PANEL1_BASE", "http://139.99.69.196")
PANEL1_LOGIN_PAGE = f"{PANEL1_BASE}/ints/login"
PANEL1_SIGNIN_URL = f"{PANEL1_BASE}/ints/signin"
PANEL1_CDR_URL   = f"{PANEL1_BASE}/ints/client/SMSCDRStats"
PANEL1_DATA_URL  = f"{PANEL1_BASE}/ints/client/res/data_smscdr.php"
PANEL1_USERNAME  = os.environ.get("PANEL1_USER", "Ahnaf044")
PANEL1_PASSWORD  = os.environ.get("PANEL1_PASS", "Ahnaf0442#")

# ── Panel 2: PROTON ──
PANEL2_BASE      = os.environ.get("PANEL2_BASE", "http://109.236.84.81")
PANEL2_LOGIN_PAGE = f"{PANEL2_BASE}/ints/login"
PANEL2_SIGNIN_URL = f"{PANEL2_BASE}/ints/signin"
PANEL2_CDR_URL   = f"{PANEL2_BASE}/ints/client/SMSCDRStats"
PANEL2_DATA_URL  = f"{PANEL2_BASE}/ints/client/res/data_smscdr.php"
PANEL2_USERNAME  = os.environ.get("PANEL2_USER", "Ahnaf044")
PANEL2_PASSWORD  = os.environ.get("PANEL2_PASS", "Ahnaf0443#")

# ── Panel 3: Konekta ──
PANEL3_BASE      = os.environ.get("PANEL3_BASE", "https://konektapremium.net")
PANEL3_LOGIN_PAGE = f"{PANEL3_BASE}/sign-in"
PANEL3_SIGNIN_URL = f"{PANEL3_BASE}/signin"
PANEL3_CDR_URL   = f"{PANEL3_BASE}/client/SMSCDRStats"
PANEL3_DATA_URL  = f"{PANEL3_BASE}/client/res/data_smscdr.php"
PANEL3_USERNAME  = os.environ.get("PANEL3_USER", "Ahnaf044")
PANEL3_PASSWORD  = os.environ.get("PANEL3_PASS", "Ahnaf0445#")

# ── Panel 4: GREEN ──
PANEL4_BASE      = os.environ.get("PANEL4_BASE", "http://139.99.9.4")
PANEL4_LOGIN_PAGE = f"{PANEL4_BASE}/ints/login"
PANEL4_SIGNIN_URL = f"{PANEL4_BASE}/ints/signin"
PANEL4_CDR_URL   = f"{PANEL4_BASE}/ints/client/SMSCDRStats"
PANEL4_DATA_URL  = f"{PANEL4_BASE}/ints/client/res/data_smscdr.php"
PANEL4_USERNAME  = os.environ.get("PANEL4_USER", "Ahnaf044")
PANEL4_PASSWORD  = os.environ.get("PANEL4_PASS", "Ahnaf0444#")

# ── Panel 5: LAMIX ──
PANEL5_BASE      = os.environ.get("PANEL5_BASE", "http://51.210.208.26")
PANEL5_LOGIN_PAGE = f"{PANEL5_BASE}/ints/login"
PANEL5_SIGNIN_URL = f"{PANEL5_BASE}/ints/signin"
PANEL5_CDR_URL   = f"{PANEL5_BASE}/ints/client/SMSCDRStats"
PANEL5_DATA_URL  = f"{PANEL5_BASE}/ints/client/res/data_smscdr.php"
PANEL5_USERNAME  = os.environ.get("PANEL5_USER", "Ahnaf044")
PANEL5_PASSWORD  = os.environ.get("PANEL5_PASS", "Ahnaf0449#")

# ── Channels & Groups ──
MAIN_CHANNEL        = os.environ.get("MAIN_CHANNEL", "@traffic_zone_sms")
MAIN_CHANNEL_LINK   = os.environ.get("MAIN_CHANNEL_LINK", "https://t.me/traffic_zone_sms")
BACKUP_CHANNEL      = os.environ.get("BACKUP_CHANNEL", "@traffic_zone_backup")
BACKUP_CHANNEL_LINK = os.environ.get("BACKUP_CHANNEL_LINK", "https://t.me/traffic_zone_backup")
THIRD_CHANNEL       = os.environ.get("THIRD_CHANNEL", "@traffic_zone_methods")
THIRD_CHANNEL_LINK  = os.environ.get("THIRD_CHANNEL_LINK", "ttps://t.me/traffic_zone_methods")
FOURTH_CHANNEL      = os.environ.get("FOURTH_CHANNEL", "@traffic_zone_chat")
FOURTH_CHANNEL_LINK = os.environ.get("FOURTH_CHANNEL_LINK", "https://t.me/traffic_zone_chat")
OTP_GROUP_LINK      = os.environ.get("OTP_GROUP_LINK", "https://t.me/traffics_zone_otp")
OTP_GROUP_ID        = int(os.environ.get("OTP_GROUP_ID", "-1003848079333"))
FORCE_CHANNELS      = [x.strip() for x in os.environ.get("FORCE_CHANNELS", "@traffic_zone_sms,@traffic_zone_backup,@traffic_zone_methods,@traffic_zone_chat").split(",")]

# ── Database & Server ──
DATABASE_URL     = os.environ.get("DATABASE_URL", "postgresql://neondb_owner:npg_ocasy6rIX2vR@ep-cold-darkness-ak558puk.c-3.us-west-2.aws.neon.tech/neondb?sslmode=require")
PORT             = int(os.environ.get("PORT", 8080))
POLL_INTERVAL    = int(os.environ.get("POLL_INTERVAL", "5"))
FLOOD_LIMIT      = 5
FLOOD_WINDOW     = 10
NUMBER_COOLDOWN  = 30
LOGIN_MIN_INTERVAL = 60

# ══════════════════════════════════════════════════════════════
#                        LOGGING
# ══════════════════════════════════════════════════════════════

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    level=logging.INFO,
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("aiohttp.access").setLevel(logging.WARNING)
logging.getLogger("telegram.ext").setLevel(logging.WARNING)
logging.getLogger("aiohttp.client").setLevel(logging.WARNING)

# ══════════════════════════════════════════════════════════════
#                      GLOBAL STATE
# ══════════════════════════════════════════════════════════════

USER_STATE  = {}
flood_data  = {}
otp_cache   = set()
maintenance = False
ADMIN_IDS   = list(BASE_ADMIN_IDS)

worker_info = {
    "running":         False,
    "logged_in":       False,
    "logged_in_p2":    False,
    "logged_in_p3":    False,
    "logged_in_p4":    False,
    "logged_in_p5":    False,
    "last_otp":        "—",
    "otps_today":      0,
    "last_login":      "—",
    "last_login_p2":   "—",
    "last_login_p3":   "—",
    "last_login_p4":   "—",
    "last_login_p5":   "—",
    "errors":          0,
    "login_errors":    0,
    "login_errors_p2": 0,
    "login_errors_p3": 0,
    "login_errors_p4": 0,
    "login_errors_p5": 0,
    "started_at":      datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
}

_SC = str.maketrans(
    "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789",
    ("ᴀʙᴄᴅᴇꜰɢʜɪᴊᴋʟᴍɴᴏᴘǫʀꜱᴛᴜᴠᴡxʏᴢ" * 2) + "0123456789"
)

def sc(t: str) -> str:
    return t.translate(_SC)

# ══════════════════════════════════════════════════════════════
#          SERVICE EMOJI + ABBREVIATION MAP
# ══════════════════════════════════════════════════════════════

SERVICE_MAP = {
    "facebook":            ("📘", "FB"),
    "whatsapp":            ("💬", "WA"),
    "whatsapp business":   ("💼", "WAB"),
    "whatsapp businesses": ("💼", "WAB"),
    "telegram":            ("✈️",  "TG"),
    "imo":                 ("💭", "IMO"),
    "instagram":           ("📸", "IG"),
    "apple":               ("🍎", "APL"),
    "google":              ("🔍", "GG"),
    "microsoft":           ("🪟", "MS"),
    "teams":               ("🧑‍🤝‍🧑", "TMS"),
    "tiktok":              ("🎵", "TT"),
    "bkash":               ("🏦", "BK"),
    "rocket":              ("🚀", "RKT"),
    "bybit":               ("📈", "BB"),
    "binance":             ("💱", "BNB"),
    "melbet":              ("🌟", "MLB"),
    "snapchat":            ("👻", "SC"),
    "uber":                ("🚗", "UBR"),
    "paypal":              ("💵", "PP"),
    "discord":             ("🎬", "DC"),
    "amazon":              ("🌟", "AMZ"),
    "viber":               ("💜", "VB"),
    "linkedin":            ("💼", "LI"),
    "line":                ("🔒", "LN"),
    "wechat":              ("🌟", "WC"),
    "twitter":             ("🐦", "TW"),
    "twitter/x":           ("🐦", "TW"),
    "reddit":              ("👽", "RDT"),
    "pinterest":           ("📌", "PIN"),
    "twitch":              ("🎮", "TWC"),
    "zoom":                ("📹", "ZM"),
    "signal":              ("💬", "SG"),
    "slack":               ("💻", "SLK"),
    "skype":               ("☎️",  "SKP"),
    "netflix":             ("🎥", "NFX"),
    "spotify":             ("🎵", "SPT"),
    "amazon prime":        ("📺", "AMP"),
    "hoichoi":             ("🍿", "HOI"),
    "daraz":               ("📦", "DRZ"),
    "foodpanda":           ("🐼", "FP"),
    "pathao":              ("🛵", "PTH"),
    "aliexpress":          ("🛒", "AEX"),
    "shopee":              ("🛍️",  "SHP"),
    "payoneer":            ("💳", "PYN"),
    "wise":                ("🦉", "WIS"),
    "chatgpt":             ("🤖", "GPT"),
    "notion":              ("📓", "NOT"),
    "github":              ("🐙", "GH"),
    "canva":               ("🖌️",  "CNV"),
    "figma":               ("🎨", "FGM"),
    "upwork":              ("💼", "UPW"),
    "fiverr":              ("🟢", "FVR"),
    "yahoo":               ("🌐", "YHO"),
    "dropbox":             ("☁️",  "DBX"),
    "coursera":            ("📚", "CRS"),
    "duolingo":            ("🗣️",  "DUO"),
    "okx":                 ("⚫", "OKX"),
    "bitget":              ("🔷", "BGT"),
    "coinbase":            ("🔵", "CB"),
    "kraken":              ("🐙", "KRK"),
    "other":               ("📱", "OTH"),
}

def get_service_info(service: str) -> tuple:
    key = service.lower().strip()
    if key in SERVICE_MAP:
        return SERVICE_MAP[key]
    for k, v in SERVICE_MAP.items():
        if k in key or key in k:
            return v
    abbr = service.strip()[:3].upper() if service.strip() else "OTH"
    return ("📱", abbr)

# ══════════════════════════════════════════════════════════════
#          COUNTRY FLAG + NAME HELPERS
# ══════════════════════════════════════════════════════════════

def iso_to_flag(iso: str) -> str:
    try:
        return "".join(chr(ord(c) + 127397) for c in iso.upper()[:2])
    except Exception:
        return "🌐"

def iso_to_name(iso: str) -> str:
    try:
        return pycountry.countries.get(alpha_2=iso).name
    except Exception:
        return iso

COUNTRY_SHORT = {
    "US": "USA", "GB": "UK", "AE": "UAE", "RU": "RUS", "DE": "GER",
    "FR": "FRA", "IN": "IND", "CN": "CHN", "JP": "JPN", "BR": "BRA",
    "MG": "MDG", "VE": "VEN", "NG": "NGA", "PH": "PHL", "ID": "IDN",
    "PK": "PAK", "BD": "BGD", "KE": "KEN", "GH": "GHA", "TZ": "TZA",
    "ET": "ETH", "CD": "COD", "MX": "MEX", "AR": "ARG", "CO": "COL",
    "SA": "SAU", "TR": "TUR", "TH": "THA", "VN": "VNM", "MY": "MYS",
    "ZA": "ZAF", "EG": "EGY", "MA": "MAR", "DZ": "DZA", "TN": "TUN",
    "UA": "UKR", "PL": "POL", "IT": "ITA", "ES": "ESP", "PT": "PRT",
    "NL": "NLD", "BE": "BEL", "SE": "SWE", "NO": "NOR", "FI": "FIN",
    "DK": "DNK", "CH": "CHE", "AT": "AUT", "CZ": "CZE", "HU": "HUN",
    "RO": "ROU", "BG": "BGR", "HR": "HRV", "RS": "SRB", "SK": "SVK",
    "KZ": "KAZ", "UZ": "UZB", "BY": "BLR", "MD": "MDA", "GE": "GEO",
    "AM": "ARM", "AZ": "AZE", "KG": "KGZ", "TJ": "TJK", "TM": "TKM",
    "CA": "CAN", "AU": "AUS", "NZ": "NZL", "SG": "SGP", "KR": "KOR",
    "HK": "HKG", "TW": "TWN", "IQ": "IRQ", "IR": "IRN", "IL": "ISR",
    "JO": "JOR", "LB": "LBN", "KW": "KWT", "QA": "QAT", "BH": "BHR",
    "OM": "OMN", "YE": "YEM", "SY": "SYR",
}

def get_country_short(iso: str) -> str:
    return COUNTRY_SHORT.get(iso.upper(), iso.upper()[:3])

def parse_phone(raw: str):
    clean = re.sub(r"\D", "", str(raw))
    if not (7 <= len(clean) <= 15):
        return None, None, None, None
    try:
        p   = phonenumbers.parse("+" + clean)
        iso = region_code_for_number(p)
        if not iso:
            return clean, None, None, None
        name = iso_to_name(iso)
        dial = country_code_for_region(iso)
        return clean, iso, name, dial
    except Exception:
        return clean, None, None, None

def mask_number(number: str) -> str:
    clean = re.sub(r"\D", "", str(number))
    if len(clean) >= 9:
        return f"{clean[:3]}•••••{clean[-3:]}"
    if len(clean) >= 6:
        return f"{clean[:3]}•••{clean[-3:]}"
    return f"{clean}•••"

def detect_phone_column(df: pd.DataFrame):
    priority = {"number", "phone", "phone number", "msisdn", "mobile", "tel", "telephone"}
    for col in df.columns:
        if col.strip().lower() in priority:
            return col
    for col in df.columns:
        sample = df[col].dropna().astype(str).head(20)
        ratio  = sample.str.replace(r"\D", "", regex=True).str.len().between(7, 15).mean()
        if ratio >= 0.6:
            return col
    return None

def load_file_df(data: bytes, name: str) -> pd.DataFrame:
    n = name.lower()
    if n.endswith(".csv"):
        return pd.read_csv(BytesIO(data))
    if n.endswith(".xlsx"):
        return pd.read_excel(BytesIO(data), engine="openpyxl")
    if n.endswith(".xls"):
        return pd.read_excel(BytesIO(data), engine="xlrd")
    raise ValueError("unsupported format")

def extract_numbers_smart(data: bytes, name: str) -> dict:
    groups  = {}
    unknown = []
    dupes   = 0
    total   = 0
    seen    = set()
    n       = name.lower()
    if n.endswith((".csv", ".xlsx", ".xls")):
        try:
            df  = load_file_df(data, name)
            col = detect_phone_column(df)
            if col:
                raws = df[col].dropna().astype(str).tolist()
            else:
                raws = []
                for c2 in df.columns:
                    raws += df[c2].dropna().astype(str).tolist()
        except Exception:
            raws = data.decode("utf-8", errors="ignore").splitlines()
    else:
        raws = data.decode("utf-8", errors="ignore").splitlines()
    for raw in raws:
        raw = str(raw).strip()
        if not raw:
            continue
        total += 1
        clean, iso, cname, dial = parse_phone(raw)
        if clean is None:
            continue
        if clean in seen:
            dupes += 1
            continue
        seen.add(clean)
        if iso:
            if iso not in groups:
                groups[iso] = {"name": cname, "flag": iso_to_flag(iso), "dial": dial, "numbers": []}
            groups[iso]["numbers"].append(clean)
        else:
            unknown.append(clean)
    return {"groups": groups, "unknown": unknown, "dupes": dupes, "total": total}

def service_abbrev(service: str) -> str:
    _, short = get_service_info(service)
    return short

# ══════════════════════════════════════════════════════════════
#                        DATABASE
# ══════════════════════════════════════════════════════════════

_db_pool = None

async def get_pool():
    global _db_pool
    if _db_pool is None:
        _db_pool = await asyncpg.create_pool(DATABASE_URL, min_size=2, max_size=10, command_timeout=30)
    return _db_pool

async def db_execute(sql, *args):
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.execute(sql, *args)

async def db_fetchone(sql, *args):
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.fetchrow(sql, *args)

async def db_fetchall(sql, *args):
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.fetch(sql, *args)

async def db_fetchval(sql, *args):
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.fetchval(sql, *args)

async def init_db():
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id    BIGINT PRIMARY KEY,
                username   TEXT    DEFAULT '',
                first_name TEXT    DEFAULT '',
                joined_at  TIMESTAMP DEFAULT NOW(),
                is_banned  BOOLEAN DEFAULT FALSE
            );
            CREATE TABLE IF NOT EXISTS otp_history (
                id         BIGSERIAL PRIMARY KEY,
                hash       TEXT    UNIQUE NOT NULL,
                number     TEXT,
                otp        TEXT,
                service    TEXT,
                sms        TEXT,
                range_name TEXT,
                added_at   TIMESTAMP DEFAULT NOW()
            );
            CREATE TABLE IF NOT EXISTS traffic (
                id          BIGSERIAL PRIMARY KEY,
                range_name  TEXT,
                number      TEXT,
                sms         TEXT,
                otp         TEXT,
                service     TEXT,
                received_at TEXT
            );
            CREATE TABLE IF NOT EXISTS numbers (
                id       BIGSERIAL PRIMARY KEY,
                country  TEXT    NOT NULL,
                flag     TEXT    DEFAULT '',
                number   TEXT    NOT NULL UNIQUE,
                service  TEXT    DEFAULT 'All',
                is_used  BOOLEAN DEFAULT FALSE,
                used_by  BIGINT  DEFAULT NULL,
                use_date TIMESTAMP DEFAULT NULL
            );
            CREATE TABLE IF NOT EXISTS cooldowns (
                user_id   BIGINT PRIMARY KEY,
                ts        BIGINT
            );
            CREATE TABLE IF NOT EXISTS settings (
                key   TEXT PRIMARY KEY,
                value TEXT NOT NULL DEFAULT ''
            );
            CREATE INDEX IF NOT EXISTS idx_otp_hash     ON otp_history(hash);
            CREATE INDEX IF NOT EXISTS idx_nums_country ON numbers(country);
            CREATE INDEX IF NOT EXISTS idx_nums_used    ON numbers(is_used);
            CREATE INDEX IF NOT EXISTS idx_nums_service ON numbers(service);
            CREATE INDEX IF NOT EXISTS idx_users_banned ON users(is_banned);
        """)
        try:
            await conn.execute("ALTER TABLE numbers ADD COLUMN IF NOT EXISTS flag TEXT DEFAULT ''")
        except Exception:
            pass
    logger.info("DB ready")

async def get_setting(key, default=""):
    row = await db_fetchone("SELECT value FROM settings WHERE key=$1", key)
    return row["value"] if row else default

async def set_setting(key, value):
    await db_execute(
        "INSERT INTO settings (key,value) VALUES ($1,$2) ON CONFLICT (key) DO UPDATE SET value=EXCLUDED.value",
        key, value,
    )

# ══════════════════════════════════════════════════════════════
#                     UI HELPERS
# ══════════════════════════════════════════════════════════════

CHANNEL_LABELS = {
    "@traffic_zone_sms":    ("MAIN CHANNEL", "https://t.me/traffic_zone_sms"),
    "@traffic_zone_backup": ("BACKUP",        "https://t.me/traffic_zone_backup"),
    "@binary_sms_m":        ("METHOD",        "https://t.me/binary_sms_m"),
    "@binary_sms_c":        ("CHAT",          "https://t.me/binary_sms_c"),
}

DEFAULT_SERVICES = [
    "WhatsApp", "Telegram", "Instagram", "Facebook", "Google",
    "TikTok", "Twitter/X", "Snapchat", "Discord", "Line",
    "WeChat", "Viber", "Signal", "Binance", "Bybit",
    "OKX", "Bitget", "Coinbase", "Kraken", "IMO",
    "Apple", "Microsoft", "ChatGPT", "Bkash", "Rocket",
    "PayPal", "Amazon", "Netflix", "Spotify", "Other",
]

def _btn(text, *, cb=None, url=None, style=None, copy=None):
    # `style` accepted for backward-compat but NOT forwarded to Telegram
    if copy is not None:
        return InlineKeyboardButton(text, copy_text=CopyTextButton(copy))
    if url is not None:
        return InlineKeyboardButton(text, url=url)
    return InlineKeyboardButton(text, callback_data=cb)

def _markup(rows):
    return InlineKeyboardMarkup(rows)

def join_gate_markup(statuses):
    rows = []
    pair = []
    for channel, (label, link) in CHANNEL_LABELS.items():
        joined = statuses.get(channel, False)
        btn    = _btn(label, cb=f"noop_joined__{channel}", style="primary") if joined else _btn(label, url=link, style="danger")
        pair.append(btn)
        if len(pair) == 2:
            rows.append(pair)
            pair = []
    if pair:
        rows.append(pair)
    rows.append([_btn("ᴏᴛᴘ ɢʀᴏᴜᴘ", url=OTP_GROUP_LINK, style="primary")])
    rows.append([_btn("ᴠᴇʀɪꜰʏ", cb="check_join", style="success")])
    return _markup(rows)

def main_menu_markup(user_id=None):
    rows = [
        [
            _btn("ɢᴇᴛ ɴᴜᴍʙᴇʀ",   cb="menu_get_number",  style="success"),
            _btn("ʟɪᴠᴇ ᴛʀᴀꜰꜰɪᴄ", cb="menu_live_traffic", style="danger"),
        ],
        [_btn("ᴏᴛᴘ ɢʀᴏᴜᴘ", url=OTP_GROUP_LINK, style="primary")],
    ]
    if user_id and is_admin(user_id):
        rows.append([_btn("ᴀᴅᴍɪɴ ᴘᴀɴᴇʟ", cb="menu_admin", style="danger")])
    return _markup(rows)

def stock_markup():
    return _markup([[
        _btn("📲 ɢᴇᴛ ɴᴜᴍʙᴇʀ", url=BOT_LINK,       style="success"),
        _btn("📡 ᴏᴛᴘ ɢʀᴏᴜᴘ",   url=OTP_GROUP_LINK, style="primary"),
    ]])

def number_assigned_markup(country, service, num_id):
    return _markup([
        [
            _btn("ᴄʜᴀɴɢᴇ ɴᴜᴍʙᴇʀ",  cb=f"chgn__{country}__{service}__{num_id}", style="success"),
            _btn("ᴄʜᴀɴɢᴇ ᴄᴏᴜɴᴛʀʏ", cb=f"gns__{service}",                       style="primary"),
        ],
        [_btn("📡 ᴏᴛᴘ ɢʀᴏᴜᴘ", url=OTP_GROUP_LINK, style="primary")],
        [_btn("ʙᴀᴄᴋ", cb="menu_back", style="danger")],
    ])

def admin_markup():
    return _markup([
        [
            _btn("ᴀᴅᴅ ɴᴜᴍʙᴇʀꜱ",    cb="adm_add_numbers",    style="success"),
            _btn("ᴅᴇʟᴇᴛᴇ ɴᴜᴍʙᴇʀꜱ", cb="adm_delete_numbers", style="danger"),
        ],
        [_btn("ꜱᴛᴀᴛᴜꜱ", cb="adm_status", style="primary")],
        [_btn("ʙᴀᴄᴋ",   cb="menu_back",  style="danger")],
    ])

def back_to_menu():
    return _markup([[_btn("ʙᴀᴄᴋ", cb="menu_back", style="danger")]])

def back_to_admin():
    return _markup([[_btn("ʙᴀᴄᴋ", cb="adm_back", style="danger")]])

def cancel_state_markup(back_cb="adm_back"):
    return _markup([[
        _btn("ᴄᴀɴᴄᴇʟ", cb="adm_cancel_state", style="danger"),
        _btn("ʙᴀᴄᴋ",   cb=back_cb,            style="danger"),
    ]])

def method_picker_markup():
    return _markup([
        [
            _btn("ᴜᴘʟᴏᴀᴅ ꜰɪʟᴇ",   cb="adm_addmethod_file", style="primary"),
            _btn("ᴛʏᴘᴇ ɴᴜᴍʙᴇʀꜱ", cb="adm_addmethod_type", style="primary"),
        ],
        [_btn("ᴄᴀɴᴄᴇʟ", cb="adm_cancel_state", style="danger")],
    ])

def service_picker_markup():
    buttons = []
    row_buf = []
    for svc in DEFAULT_SERVICES:
        emoji, _ = get_service_info(svc)
        row_buf.append(_btn(f"{emoji} {sc(svc)}", cb=f"adm_svc__{svc}", style="primary"))
        if len(row_buf) == 3:
            buttons.append(row_buf)
            row_buf = []
    if row_buf:
        buttons.append(row_buf)
    buttons.append([_btn("✏️ ᴄᴜꜱᴛᴏᴍ", cb="adm_svc_custom", style="primary")])
    buttons.append([_btn("ᴄᴀɴᴄᴇʟ", cb="adm_cancel_state", style="danger")])
    return _markup(buttons)

async def build_service_grid():
    rows = await db_fetchall(
        "SELECT service, COUNT(*) AS cnt FROM numbers WHERE is_used=FALSE GROUP BY service ORDER BY service"
    )
    if not rows:
        return None, None
    buttons = []
    row_buf = []
    for r in rows:
        emoji, _ = get_service_info(r["service"])
        row_buf.append(_btn(f"{emoji} {sc(r['service'])}", cb=f"gns__{r['service']}", style="success"))
        if len(row_buf) == 2:
            buttons.append(row_buf)
            row_buf = []
    if row_buf:
        buttons.append(row_buf)
    buttons.append([_btn("ʙᴀᴄᴋ", cb="menu_back", style="danger")])
    return rows, _markup(buttons)

async def build_country_grid(service):
    rows = await db_fetchall(
        "SELECT country, flag, COUNT(*) AS cnt FROM numbers WHERE is_used=FALSE AND service=$1 GROUP BY country, flag ORDER BY country",
        service,
    )
    if not rows:
        return None, None
    buttons = []
    row_buf = []
    for r in rows:
        flag  = r["flag"] or ""
        label = f"{flag} {sc(r['country'])}".strip()
        row_buf.append(_btn(label, cb=f"gnc__{r['country']}__{service}", style="success"))
        if len(row_buf) == 2:
            buttons.append(row_buf)
            row_buf = []
    if row_buf:
        buttons.append(row_buf)
    buttons.append([_btn("ʙᴀᴄᴋ", cb="menu_get_number", style="danger")])
    return rows, _markup(buttons)

async def build_delete_service_grid():
    rows = await db_fetchall(
        "SELECT service, COUNT(*) AS cnt FROM numbers GROUP BY service ORDER BY service"
    )
    if not rows:
        return None, None
    buttons = []
    row_buf = []
    for r in rows:
        emoji, _ = get_service_info(r["service"])
        row_buf.append(_btn(f"{emoji} {sc(r['service'])}", cb=f"del_svc__{r['service']}", style="danger"))
        if len(row_buf) == 2:
            buttons.append(row_buf)
            row_buf = []
    if row_buf:
        buttons.append(row_buf)
    buttons.append([_btn("🗑️ ᴀʟʟ", cb="del_svc__ALL", style="danger")])
    buttons.append([_btn("ʙᴀᴄᴋ", cb="adm_back", style="danger")])
    return rows, _markup(buttons)

async def build_delete_country_grid(service):
    if service == "ALL":
        rows = await db_fetchall("SELECT country, flag, COUNT(*) AS cnt FROM numbers GROUP BY country, flag ORDER BY country")
    else:
        rows = await db_fetchall("SELECT country, flag, COUNT(*) AS cnt FROM numbers WHERE service=$1 GROUP BY country, flag ORDER BY country", service)
    if not rows:
        return None, None
    buttons = []
    row_buf = []
    for r in rows:
        flag  = r["flag"] or ""
        label = f"{flag} {sc(r['country'])}".strip()
        row_buf.append(_btn(label, cb=f"del_cntry__{service}__{r['country']}", style="danger"))
        if len(row_buf) == 2:
            buttons.append(row_buf)
            row_buf = []
    if row_buf:
        buttons.append(row_buf)
    buttons.append([_btn("🗑️ ᴀʟʟ ᴄᴏᴜɴᴛʀɪᴇꜱ", cb=f"del_cntry__{service}__ALL", style="danger")])
    buttons.append([_btn("ʙᴀᴄᴋ", cb="adm_delete_numbers", style="danger")])
    return rows, _markup(buttons)

# ══════════════════════════════════════════════════════════════
#                   ACCESS CONTROL
# ══════════════════════════════════════════════════════════════

def is_admin(user_id):
    return user_id in ADMIN_IDS

def is_flooded(user_id):
    if is_admin(user_id):
        return False
    now     = time.time()
    history = [t for t in flood_data.get(user_id, []) if now - t < FLOOD_WINDOW]
    history.append(now)
    flood_data[user_id] = history
    return len(history) > FLOOD_LIMIT

async def register_user(user):
    await db_execute(
        "INSERT INTO users (user_id, username, first_name) VALUES ($1,$2,$3) "
        "ON CONFLICT (user_id) DO UPDATE SET username=$2, first_name=$3",
        user.id, user.username or "", user.first_name or "",
    )

async def is_banned_user(user_id):
    row = await db_fetchone("SELECT is_banned FROM users WHERE user_id=$1", user_id)
    return bool(row and row["is_banned"])

async def check_membership(bot, user_id):
    if is_admin(user_id):
        return True
    for channel in FORCE_CHANNELS:
        try:
            member = await bot.get_chat_member(channel, user_id)
            if member.status in ("left", "kicked", "banned"):
                return False
        except Exception:
            return False
    return True

async def check_membership_per_channel(bot, user_id):
    statuses = {}
    for channel in FORCE_CHANNELS:
        try:
            member = await bot.get_chat_member(channel, user_id)
            statuses[channel] = member.status in ("member", "administrator", "creator", "restricted")
        except Exception as e:
            logger.warning(f"Membership check failed {channel} user {user_id}: {e}")
            statuses[channel] = True
    return statuses

async def check_number_cooldown(user_id):
    row = await db_fetchone("SELECT ts FROM cooldowns WHERE user_id=$1", user_id)
    if row:
        elapsed = int(time.time()) - row["ts"]
        if elapsed < NUMBER_COOLDOWN:
            return NUMBER_COOLDOWN - elapsed
    return 0

async def set_number_cooldown(user_id):
    await db_execute(
        "INSERT INTO cooldowns (user_id,ts) VALUES ($1,$2) ON CONFLICT (user_id) DO UPDATE SET ts=$2",
        user_id, int(time.time()),
    )

# ══════════════════════════════════════════════════════════════
#                   OTP EXTRACTION
# ══════════════════════════════════════════════════════════════

def extract_otp(sms: str):
    if not sms:
        return None
    sms = sms.strip()
    patterns = [
        r"[Oo][Tt][Pp][\s:]*([0-9]{4,8})",
        r"[Vv]erification[\s]+[Cc]ode[\s:]*([0-9]{4,8})",
        r"[Cc]ode[\s:]*([0-9]{4,8})",
        r"[Pp]in[\s:]*([0-9]{4,8})",
        r"[Ss]ecret[\s:]*([0-9]{4,8})",
        r"[Ll]ogin[\s]+[Cc]ode[\s:]*([0-9]{4,8})",
        r"[Cc]onfirmation[\s]+[Cc]ode[\s:]*([0-9]{4,8})",
        r"[Yy]our[\s]+code[\s]*(?:is|:|\s)*([0-9]{4,8})",
        r"[Yy]our[\s]+[Oo][Tt][Pp][\s]*(?:is|:|\s)*([0-9]{4,8})",
        r"[Ll]a[\s]+[Cc]ode[\s]*(?:est|:|\s)*([0-9]{4,8})",
        r"[Ss]u[\s]+[Cc]odigo[\s]*(?:es|:|\s)*([0-9]{4,8})",
        r"(?<![0-9])[0-9]{6,8}(?![0-9])",
        r"(?<![0-9])[0-9]{4,5}(?![0-9])",
        r"([0-9]{3})[\s\-]([0-9]{3,4})",
        r"([0-9]{2})[\s\-]([0-9]{2})[\s\-]([0-9]{2,4})",
        r"驗證碼[：:\s]*([0-9]+)",
        r"验证码[：:\s]*([0-9]+)",
        r"کود[：:\s]*([0-9]+)",
        r"קוד[：:\s]*([0-9]+)",
        r"कोड[：:\s]*([0-9]+)",
        r"รหัส[：:\s]*([0-9]+)",
        r"コード[：:\s]*([0-9]+)",
        r"Mã[：:\s]*([0-9]+)",
        r"Kode[：:\s]*([0-9]+)",
        r"Mật khẩu[：:\s]*([0-9]+)",
        r"Пароль[：:\s]*([0-9]+)",
        r"رمز[：:\s]*([0-9]+)",
        r"[Tt]elegram[\s]+[Cc]ode[\s:]*([0-9]{5})",
        r"[Ww]hats[Aa]pp[\s]+[Cc]ode[\s:]*([0-9]{3}[\s\-][0-9]{3})",
        r"[Gg]oogle[\s]+[Cc]ode[\s:]*([0-9]{6})",
        r"[Ff]acebook[\s]+[Cc]ode[\s:]*([0-9]{5})",
        r"([0-9]{4,8})[\s]*$",
        r" код [:]? ([0-9]+)",
        r"code is[:\s]+([0-9]+)",
        r"code[:\s]+([0-9]+)",
        r"otp[:\s]+([0-9]+)",
        r"pin[:\s]+([0-9]+)",
        r"mã[:\s]+([0-9]+)",
        r"رمز عبور ([0-9]+)",
        r"пароль ([0-9]+)",
    ]
    for pattern in patterns:
        try:
            matches = re.findall(pattern, sms, re.IGNORECASE)
            for match in matches:
                otp = ''.join(match) if isinstance(match, tuple) else match
                otp = re.sub(r'\D', '', otp)
                if 4 <= len(otp) <= 8:
                    logger.debug(f"OTP extracted: {otp}")
                    return otp
        except Exception:
            continue
    fallback = re.findall(r'\b(\d{4,8})\b', sms)
    for num in fallback:
        if 4 <= len(num) <= 8:
            return num
    return None

# ══════════════════════════════════════════════════════════════
#                MESSAGING HELPERS
# ══════════════════════════════════════════════════════════════

async def send_msg(bot, chat_id, text, reply_markup=None):
    return await bot.send_message(
        chat_id=chat_id, text=text,
        parse_mode=ParseMode.HTML, reply_markup=reply_markup,
        disable_web_page_preview=True,
    )

async def edit_msg(query, text, reply_markup=None):
    try:
        await query.edit_message_text(
            text=text, parse_mode=ParseMode.HTML,
            reply_markup=reply_markup, disable_web_page_preview=True,
        )
    except Exception:
        pass

async def notify_admins(app, text):
    for aid in ADMIN_IDS:
        try:
            await app.bot.send_message(
                chat_id=aid, text=text,
                parse_mode=ParseMode.HTML, disable_web_page_preview=True,
            )
        except Exception:
            pass

async def broadcast_stock(app, country, flag, service, count, numbers_list):
    emoji, _   = get_service_info(service)
    filename   = f"{flag} {sc(country)} — {sc(service)}.txt".replace("/", "-")
    file_bytes = "\n".join(numbers_list).encode("utf-8")
    caption    = (
        f"📦 ɴᴇᴡ ꜱᴛᴏᴄᴋ ᴀᴅᴅᴇᴅ\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🌍 ᴄᴏᴜɴᴛʀʏ  : {flag} {sc(country)}\n"
        f"{emoji} ꜱᴇʀᴠɪᴄᴇ  : {sc(service)}\n"
        f"📱 ɴᴜᴍʙᴇʀꜱ  : {count}\n"
        f"━━━━━━━━━━━━━━━━━━━━"
    )
    markup = stock_markup()
    try:
        await app.bot.send_document(
            chat_id=MAIN_CHANNEL,
            document=InputFile(BytesIO(file_bytes), filename=filename),
            caption=caption, parse_mode=ParseMode.HTML, reply_markup=markup,
        )
    except Exception as e:
        logger.error(f"Channel notify: {e}")
    all_users = await db_fetchall("SELECT user_id FROM users WHERE is_banned=FALSE")
    for row in all_users:
        uid = row["user_id"]
        if uid in ADMIN_IDS:
            continue
        try:
            await app.bot.send_document(
                chat_id=uid,
                document=InputFile(BytesIO(file_bytes), filename=filename),
                caption=caption, parse_mode=ParseMode.HTML, reply_markup=markup,
            )
            await asyncio.sleep(0.05)
        except Exception:
            pass

# ══════════════════════════════════════════════════════════════
#   ✦ PREMIUM OTP MESSAGE — MATCHES PICTURE EXACTLY ✦
# ══════════════════════════════════════════════════════════════

def build_otp_markup(otp: str, sms: str) -> InlineKeyboardMarkup:
    return _markup([
        [
            _btn(f"🛡️ {otp}", copy=otp, style="success"),
        ],
        [
            _btn("📲  N U M B E R", url=NUMBER_LINK,  style="success"),
            _btn("📡  M E T H O D S", url=METHODS_LINK, style="primary"),
        ],
    ])

def format_otp_message(row: dict, otp: str, panel_name: str = "") -> tuple:
    number_raw       = row.get("number", "").strip()
    clean            = re.sub(r"\D", "", str(number_raw))
    _, iso, cname, _ = parse_phone(clean)
    flag             = iso_to_flag(iso) if iso else "🌐"
    sms_txt          = (row.get("sms") or "").strip()
    raw_service      = (row.get("service") or "Other").strip()

    svc_emoji, svc_short = get_service_info(raw_service)
    country_short        = get_country_short(iso) if iso else "UNK"
    lang_map = {"US":"EN","GB":"EN","CA":"EN","AU":"EN","FR":"FR","DE":"DE","ES":"ES","IT":"IT","PT":"PT","BR":"PT","RU":"RU","CN":"ZH","JP":"JA","KR":"KO","BD":"BN","IN":"HI","SA":"AR","AE":"AR","TR":"TR","ID":"ID","VN":"VI","TH":"TH"}
    lang   = lang_map.get((iso or "").upper(), "EN")
    first3 = clean[:3] if len(clean) >= 3 else clean
    last3  = clean[-3:] if len(clean) >= 3 else ""

    text = (
        f"<b>{svc_short}</b>{svc_emoji} <b>{country_short}</b>{flag} {first3}❖𝕾𝖆𝖆𝖉❖{last3} #{lang}"
    )

    markup = build_otp_markup(otp, sms_txt)
    return text, markup

def number_display_text(number, country_name, flag, service):
    emoji, _  = get_service_info(service)
    display   = f"+{number}" if not str(number).startswith("+") else number
    return (
        f"┌─ ɴᴜᴍʙᴇʀ ᴀꜱꜱɪɢɴᴇᴅ\n"
        f"├─❏ 📞 ɴᴜᴍʙᴇʀ   : <code>{display}</code>\n"
        f"├─❏ 🌍 ᴄᴏᴜɴᴛʀʏ  : {flag} {sc(country_name)}\n"
        f"├─❏ {emoji} ꜱᴇʀᴠɪᴄᴇ  : {sc(service)}\n"
        f"└─❏ ⏳ ᴡᴀɪᴛɪɴɢ ꜰᴏʀ ᴏᴛᴘ..."
    )

def number_changed_text(number, country_name, flag, service):
    emoji, _  = get_service_info(service)
    display   = f"+{number}" if not str(number).startswith("+") else number
    return (
        f"┌─ ɴᴜᴍʙᴇʀ ᴄʜᴀɴɢᴇᴅ\n"
        f"├─❏ 📞 ɴᴜᴍʙᴇʀ   : <code>{display}</code>\n"
        f"├─❏ 🌍 ᴄᴏᴜɴᴛʀʏ  : {flag} {sc(country_name)}\n"
        f"├─❏ {emoji} ꜱᴇʀᴠɪᴄᴇ  : {sc(service)}\n"
        f"└─❏ ⏳ ᴡᴀɪᴛɪɴɢ ꜰᴏʀ ᴏᴛᴘ..."
    )

def admin_text():
    return "┌─ ᴀᴅᴍɪɴ ᴘᴀɴᴇʟ\n├─❏ ᴍᴀɴᴀɢᴇ ɴᴜᴍʙᴇʀ ᴅᴀᴛᴀʙᴀꜰᴇ\n└─❏"

async def status_text():
    total   = await db_fetchval("SELECT COUNT(*) FROM numbers") or 0
    avail   = await db_fetchval("SELECT COUNT(*) FROM numbers WHERE is_used=FALSE") or 0
    users   = await db_fetchval("SELECT COUNT(*) FROM users") or 0
    otps    = await db_fetchval("SELECT COUNT(*) FROM otp_history") or 0
    def st(k): return "🟢 ᴏɴʟɪɴᴇ" if worker_info[k] else "🔴 ᴏꜰꜰʟɪɴᴇ"
    return (
        f"┌─ ꜱᴛᴀᴛᴜꜱ\n"
        f"├─❏ EMO SMS : {st('logged_in')} | {worker_info['last_login']}\n"
        f"├─❏ PROTON  : {st('logged_in_p2')} | {worker_info['last_login_p2']}\n"
        f"├─❏ ᴋᴏɴᴇᴋᴛᴀ : {st('logged_in_p3')} | {worker_info['last_login_p3']}\n"
        f"├─❏ GREEN   : {st('logged_in_p4')} | {worker_info['last_login_p4']}\n"
        f"├─❏ LAMIX   : {st('logged_in_p5')} | {worker_info['last_login_p5']}\n"
        f"├─❏ ᴏᴛᴘꜱ ᴛᴏᴅᴀʏ : {worker_info['otps_today']}\n"
        f"├─❏ ʟᴀꜱᴛ ᴏᴛᴘ   : {worker_info['last_otp']}\n"
        f"├─❏ ɴᴜᴍʙᴇʀꜱ    : {total} ᴛᴏᴛᴀʟ / {avail} ᴀᴠᴀɪʟ\n"
        f"├─❏ ᴜꜱᴇʀꜱ       : {users}\n"
        f"├─❏ ᴏᴛᴘ ʜɪꜱᴛᴏʀʏ : {otps}\n└─❏"
    )

def solve_captcha(html):
    try:
        soup      = BeautifulSoup(html, "html.parser")
        full_text = soup.get_text(" ", strip=True)
        m         = re.search(r"[Ww]hat\s+is\s+(\d+)\s*([\+\-*×xX÷/])\s*(\d+)\s*[=?]", full_text)
        if not m:
            for tag in soup.find_all(True):
                t = tag.get_text(strip=True)
                m = re.search(r"(\d+)\s*([\+\-*×xX÷/])\s*(\d+)\s*=\s*\?", t)
                if m:
                    break
        if m:
            a, op, b = int(m.group(1)), m.group(2).strip(), int(m.group(3))
            if op == "+":                    return str(a + b)
            if op == "-":                    return str(a - b)
            if op in ("*", "×", "x", "X"):  return str(a * b)
            if op in ("÷", "/") and b != 0: return str(a // b)
    except Exception as e:
        logger.error(f"Captcha: {e}")
    return "0"

# ══════════════════════════════════════════════════════════════
#                  PANEL SESSION CLASS
# ══════════════════════════════════════════════════════════════

class PanelSession:
    def __init__(self, base, login_page, signin_url, cdr_url, data_url,
                 username, password, name="panel"):
        self._base             = base
        self._login_page       = login_page
        self._signin_url       = signin_url
        self._cdr_url          = cdr_url
        self._data_url         = data_url
        self._username         = username
        self._password         = password
        self._name             = name
        self._dashboard_url    = cdr_url.replace("SMSCDRStats", "SMSDashboard")
        self._session          = None
        self._logged_in        = False
        self._sesskey          = ""
        self._last_login_try   = 0
        self._login_backoff    = LOGIN_MIN_INTERVAL
        self._last_activity    = 0
        self._last_ping        = 0
        self._working_data_url = None
        self._cookie_header    = ""

    async def _new_session(self):
        if self._session and not self._session.closed:
            await self._session.close()
        connector     = aiohttp.TCPConnector(ssl=False, limit=10, ttl_dns_cache=300, enable_cleanup_closed=True)
        self._session = aiohttp.ClientSession(
            connector=connector,
            headers={
                "User-Agent":      "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept-Language": "en-US,en;q=0.9",
                "Accept-Encoding": "gzip, deflate",
                "Connection":      "keep-alive",
            },
            timeout=aiohttp.ClientTimeout(total=60, connect=20),
            cookie_jar=aiohttp.CookieJar(unsafe=True),
        )
        return self._session

    async def _get_session(self):
        if self._session is None or self._session.closed:
            await self._new_session()
        return self._session

    def _can_attempt_login(self):
        return time.time() - self._last_login_try >= self._login_backoff

    def _is_login_page(self, url: str) -> bool:
        u = url.lower()
        login_path = self._login_page.split(self._base)[-1].lower()
        return login_path in u or "/sign-in" in u

    def _get_cookie_str(self) -> str:
        try:
            if not self._session:
                return ""
            cookies = {}
            for c in self._session.cookie_jar:
                cookies[c.key] = c.value
            return "; ".join(f"{k}={v}" for k, v in cookies.items())
        except Exception:
            return ""

    async def _keepalive_ping(self):
        if not self._logged_in:
            return
        now = time.time()
        if now - self._last_ping < 90:
            return
        try:
            sess = await self._get_session()
            async with sess.get(
                self._cdr_url, allow_redirects=True,
                timeout=aiohttp.ClientTimeout(total=15),
                headers={
                    "Referer": self._dashboard_url,
                    "Accept":  "text/html,application/xhtml+xml,*/*;q=0.8",
                    "Upgrade-Insecure-Requests": "1",
                },
            ) as resp:
                if self._is_login_page(str(resp.url)):
                    logger.warning(f"[{self._name}] Keepalive: session expired")
                    self._logged_in = False
                else:
                    self._last_ping     = now
                    self._last_activity = now
        except Exception as e:
            logger.warning(f"[{self._name}] Keepalive failed: {e}")

    async def login(self) -> bool:
        if not self._can_attempt_login():
            return False
        self._last_login_try = time.time()
        logger.info(f"[{self._name}] Login attempt (backoff={self._login_backoff}s)")
        try:
            sess = await self._new_session()

            async with sess.get(
                self._login_page, allow_redirects=True,
                timeout=aiohttp.ClientTimeout(total=30),
                headers={"Accept": "text/html,application/xhtml+xml,*/*;q=0.8"},
            ) as resp:
                if resp.status != 200:
                    logger.error(f"[{self._name}] Login page HTTP {resp.status}")
                    self._login_backoff = min(self._login_backoff * 2, 3600)
                    return False
                login_html = await resp.text(errors="replace")

            capt    = solve_captcha(login_html)
            payload = {"username": self._username, "password": self._password, "capt": capt}
            logger.info(f"[{self._name}] Captcha: {capt}")

            async with sess.post(
                self._signin_url, data=payload,
                allow_redirects=False,
                timeout=aiohttp.ClientTimeout(total=30),
                headers={
                    "Referer":                   self._login_page,
                    "Origin":                    self._base,
                    "Content-Type":              "application/x-www-form-urlencoded",
                    "Accept":                    "text/html,application/xhtml+xml,*/*;q=0.8",
                    "Upgrade-Insecure-Requests": "1",
                },
            ) as resp:
                location = resp.headers.get("Location", "")
                logger.info(f"[{self._name}] POST → {resp.status} Location={location}")
                if resp.status not in (301, 302, 303, 307, 308):
                    body = await resp.text(errors="replace")
                    logger.error(f"[{self._name}] No redirect. Body: {body[:200]}")
                    self._login_backoff = min(self._login_backoff * 2, 3600)
                    return False
                if self._is_login_page(location):
                    logger.error(f"[{self._name}] Rejected — back to login")
                    self._login_backoff = min(self._login_backoff * 2, 3600)
                    return False
                self._cookie_header = self._get_cookie_str()

            await asyncio.sleep(2)

            async with sess.get(
                self._cdr_url, allow_redirects=True,
                timeout=aiohttp.ClientTimeout(total=30),
                headers={
                    "Referer":                   self._dashboard_url,
                    "Accept":                    "text/html,application/xhtml+xml,*/*;q=0.8",
                    "Upgrade-Insecure-Requests": "1",
                },
            ) as cdr_resp:
                cdr_final = str(cdr_resp.url)
                logger.info(f"[{self._name}] CDR verify → {cdr_resp.status} {cdr_final}")
                if self._is_login_page(cdr_final):
                    logger.error(f"[{self._name}] CDR → login page, session rejected")
                    self._login_backoff = min(self._login_backoff * 2, 3600)
                    return False
                cdr_html = await cdr_resp.text(errors="replace")
                self._cookie_header = self._get_cookie_str()

            self._extract_sesskey(cdr_html)
            self._working_data_url = await self._discover_data_url(sess, cdr_html)

            self._logged_in      = True
            self._login_backoff  = LOGIN_MIN_INTERVAL
            self._last_activity  = time.time()
            self._last_ping      = time.time()
            worker_info["login_errors"] = 0
            logger.info(f"[{self._name}] Login OK | data={self._working_data_url}")
            return True

        except Exception as e:
            logger.error(f"[{self._name}] Login exception: {type(e).__name__}: {e}")
            self._login_backoff = min(self._login_backoff * 2, 3600)
            return False

    def _extract_sesskey(self, html: str):
        for pat in (
            r'["\']sesskey["\']\s*[,:=]\s*["\']([A-Za-z0-9+/=_\-]{10,})["\']',
            r'sesskey\s*=\s*["\']([A-Za-z0-9+/=_\-]{10,})["\']',
            r'var\s+sesskey\s*=\s*["\']([A-Za-z0-9+/=_\-]{10,})["\']',
        ):
            m = re.search(pat, html)
            if m:
                self._sesskey = m.group(1)
                logger.info(f"[{self._name}] sesskey: {self._sesskey[:12]}…")
                return
        logger.warning(f"[{self._name}] No sesskey found")

    async def _discover_data_url(self, sess, cdr_html: str) -> str:
        candidates = []
        js_pats = [
            r'url:\s*["\']([^"\']+data_smscdr\.php[^"\']*)["\']',
            r'"url"\s*:\s*"([^"]+data_smscdr\.php[^"]*)"',
            r'ajax\(["\']([^"\']+data_smscdr\.php[^"\']*)["\']',
        ]
        for pat in js_pats:
            m = re.search(pat, cdr_html)
            if m:
                url = m.group(1)
                full = url if url.startswith("http") else self._base.rstrip("/") + "/" + url.lstrip("/")
                candidates.append(full)
                break

        candidates += [
            self._data_url,
            f"{self._base}/ints/client/res/data_smscdr.php",
            f"{self._base}/client/res/data_smscdr.php",
            f"{self._base}/ints/res/data_smscdr.php",
            f"{self._base}/res/data_smscdr.php",
        ]

        seen   = set()
        unique = [u for u in candidates if not (u in seen or seen.add(u))]

        now_dt      = datetime.now()
        test_params = {
            "fdate1": now_dt.strftime("%Y-%m-01 00:00:00"),
            "fdate2": now_dt.strftime("%Y-%m-%d 23:59:59"),
            "sEcho": "1", "iColumns": "7",
            "iDisplayStart": "0", "iDisplayLength": "10",
            "sSearch": "", "iSortCol_0": "0",
            "sSortDir_0": "desc", "iSortingCols": "1",
            "_": str(int(time.time() * 1000)),
        }
        if self._sesskey:
            test_params["sesskey"] = self._sesskey

        cookie_str = self._get_cookie_str()

        for url in unique:
            try:
                logger.info(f"[{self._name}] Testing data URL: {url}")
                async with sess.get(
                    url, params=test_params,
                    allow_redirects=True,
                    timeout=aiohttp.ClientTimeout(total=15),
                    headers={
                        "Referer":          self._dashboard_url,
                        "X-Requested-With": "XMLHttpRequest",
                        "Accept":           "application/json, text/javascript, */*; q=0.01",
                        "Origin":           self._base,
                        "Cookie":           cookie_str,
                    },
                ) as resp:
                    if resp.status != 200:
                        continue
                    txt = await resp.text(errors="replace")
                    if not txt.strip():
                        continue
                    try:
                        parsed = json.loads(txt)
                        if isinstance(parsed, dict) and (
                            "aaData" in parsed or "data" in parsed or
                            any(k in parsed for k in ["records", "result", "results", "rows", "items"])
                        ):
                            logger.info(f"[{self._name}] Working URL: {url}")
                            return url
                        if isinstance(parsed, list):
                            logger.info(f"[{self._name}] Working URL (list): {url}")
                            return url
                    except Exception:
                        pass
            except Exception as e:
                logger.debug(f"[{self._name}] URL test error {url}: {e}")
                continue

        logger.warning(f"[{self._name}] No working URL found, using default: {self._data_url}")
        return self._data_url

    def _build_params(self) -> dict:
        now_dt = datetime.now()
        params = {
            "fdate1": now_dt.strftime("%Y-%m-01 00:00:00"),
            "fdate2": now_dt.strftime("%Y-%m-%d 23:59:59"),
            "frange": "", "fnum": "", "fcli": "", "fgdate": "",
            "fgmonth": "", "fgrange": "", "fgnumber": "", "fgcli": "",
            "fg": "0", "sEcho": "1", "iColumns": "7", "sColumns": "......",
            "iDisplayStart": "0", "iDisplayLength": "100",
            "mDataProp_0": "0", "sSearch_0": "", "bRegex_0": "false",
            "bSearchable_0": "true", "bSortable_0": "true",
            "mDataProp_1": "1", "sSearch_1": "", "bRegex_1": "false",
            "bSearchable_1": "true", "bSortable_1": "true",
            "mDataProp_2": "2", "sSearch_2": "", "bRegex_2": "false",
            "bSearchable_2": "true", "bSortable_2": "true",
            "mDataProp_3": "3", "sSearch_3": "", "bRegex_3": "false",
            "bSearchable_3": "true", "bSortable_3": "true",
            "mDataProp_4": "4", "sSearch_4": "", "bRegex_4": "false",
            "bSearchable_4": "true", "bSortable_4": "true",
            "mDataProp_5": "5", "sSearch_5": "", "bRegex_5": "false",
            "bSearchable_5": "true", "bSortable_5": "true",
            "mDataProp_6": "6", "sSearch_6": "", "bRegex_6": "false",
            "bSearchable_6": "true", "bSortable_6": "true",
            "sSearch": "", "bRegex": "false",
            "iSortCol_0": "0", "sSortDir_0": "desc", "iSortingCols": "1",
            "_": str(int(time.time() * 1000)),
        }
        if self._sesskey:
            params["sesskey"] = self._sesskey
        return params

    async def fetch_cdr(self):
        if not self._logged_in:
            return None, "not_logged_in"
        try:
            sess       = await self._get_session()
            params     = self._build_params()
            data_url   = self._working_data_url or self._data_url
            cookie_str = self._get_cookie_str() or self._cookie_header
            headers    = {
                "Referer":          self._dashboard_url,
                "X-Requested-With": "XMLHttpRequest",
                "Accept":           "application/json, text/javascript, */*; q=0.01",
                "Origin":           self._base,
                "Cookie":           cookie_str,
                "Cache-Control":    "no-cache",
                "Pragma":           "no-cache",
            }
            async with sess.get(
                data_url, params=params, headers=headers,
                allow_redirects=True, timeout=aiohttp.ClientTimeout(total=30),
            ) as resp:
                final = str(resp.url)
                if self._is_login_page(final):
                    self._logged_in = False
                    return None, "session_expired"
                if resp.status == 403:
                    logger.error(f"[{self._name}] 403 on {data_url} — force relogin")
                    self._working_data_url = None
                    self._logged_in        = False
                    return None, "session_expired"
                if resp.status == 404:
                    logger.error(f"[{self._name}] 404 on {data_url} — force relogin")
                    self._working_data_url = None
                    self._logged_in        = False
                    return None, "session_expired"
                if resp.status not in (200, 304):
                    logger.error(f"[{self._name}] HTTP {resp.status}")
                    return None, f"http_{resp.status}"
                text = await resp.text(errors="replace")
                logger.info(f"[{self._name}] CDR len={len(text)}")
                logger.debug(f"[{self._name}] CDR preview: {text[:200]}")
                if not text.strip():
                    return [], None
                stripped = text.strip().lower()
                if stripped.startswith("<!doctype") or stripped.startswith("<html"):
                    if len(text) < 6000:
                        if "403" in text or "forbidden" in text.lower():
                            self._working_data_url = None
                            self._logged_in        = False
                            return None, "session_expired"
                        if "login" in text.lower() or "sign-in" in text.lower():
                            self._logged_in = False
                            return None, "session_expired"
                    rows = self._parse_html_table(text)
                    if rows:
                        return rows, None
                    return None, "html_response"
                try:
                    data = json.loads(text)
                except Exception:
                    logger.error(f"[{self._name}] JSON parse failed: {text[:100]}")
                    return None, "parse_error"
                rows = self._parse_json(data)
                logger.info(f"[{self._name}] Parsed {len(rows)} rows")
                if rows:
                    logger.debug(f"[{self._name}] Sample: {rows[0]}")
                self._last_activity = time.time()
                return rows, None
        except Exception as e:
            logger.error(f"[{self._name}] fetch_cdr exception: {type(e).__name__}: {e}")
            return None, str(e)

    def _parse_json(self, data) -> list:
        rows = []
        if isinstance(data, dict):
            if "aaData" in data:
                for row in data["aaData"]:
                    if isinstance(row, list) and len(row) >= 5:
                        rows.append({"date": str(row[0]).strip(), "range": str(row[1]).strip(),
                                     "number": str(row[2]).strip(), "service": str(row[3]).strip(),
                                     "sms": str(row[4]).strip()})
                return rows
            if "data" in data:
                for item in (data["data"] if isinstance(data["data"], list) else []):
                    if isinstance(item, list) and len(item) >= 5:
                        rows.append({"date": str(item[0]).strip(), "range": str(item[1]).strip(),
                                     "number": str(item[2]).strip(), "service": str(item[3]).strip(),
                                     "sms": str(item[4]).strip()})
                    elif isinstance(item, dict):
                        rows.append(self._dict_row(item))
                return rows
            for key in ["records", "result", "results", "sms", "messages", "items", "rows"]:
                if key in data and isinstance(data[key], list):
                    for item in data[key]:
                        if isinstance(item, list) and len(item) >= 5:
                            rows.append({"date": str(item[0]).strip(), "range": str(item[1]).strip(),
                                         "number": str(item[2]).strip(), "service": str(item[3]).strip(),
                                         "sms": str(item[4]).strip()})
                        elif isinstance(item, dict):
                            rows.append(self._dict_row(item))
                    if rows:
                        return rows
        elif isinstance(data, list):
            for item in data:
                if isinstance(item, list) and len(item) >= 5:
                    rows.append({"date": str(item[0]).strip(), "range": str(item[1]).strip(),
                                 "number": str(item[2]).strip(), "service": str(item[3]).strip(),
                                 "sms": str(item[4]).strip()})
                elif isinstance(item, dict):
                    rows.append(self._dict_row(item))
        return rows

    def _dict_row(self, item: dict) -> dict:
        return {
            "date":    str(item.get("date", item.get("datetime", item.get("created_at", "")))).strip(),
            "range":   str(item.get("range", item.get("cli", item.get("sender", "")))).strip(),
            "number":  str(item.get("number", item.get("phone", item.get("msisdn", item.get("destination", ""))))).strip(),
            "service": str(item.get("service", item.get("name", item.get("app", "")))).strip(),
            "sms":     str(item.get("sms", item.get("message", item.get("text", item.get("body", ""))))).strip(),
        }

    def _parse_html_table(self, html: str) -> list:
        try:
            soup = BeautifulSoup(html, "html.parser")
            for table in soup.find_all("table"):
                rows = []
                for tr in table.find_all("tr")[1:]:
                    cells = tr.find_all(["td", "th"])
                    if len(cells) >= 5:
                        rows.append({
                            "date":    cells[0].get_text(strip=True),
                            "range":   cells[1].get_text(strip=True),
                            "number":  cells[2].get_text(strip=True),
                            "service": cells[3].get_text(strip=True),
                            "sms":     cells[4].get_text(strip=True),
                        })
                if rows:
                    return rows
        except Exception as e:
            logger.error(f"[{self._name}] HTML parse error: {e}")
        return []

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()

# ══════════════════════════════════════════════════════════════
#                   PANEL INSTANCES
# ══════════════════════════════════════════════════════════════

panel  = PanelSession(
    base=PANEL1_BASE, login_page=PANEL1_LOGIN_PAGE, signin_url=PANEL1_SIGNIN_URL,
    cdr_url=PANEL1_CDR_URL, data_url=PANEL1_DATA_URL,
    username=PANEL1_USERNAME, password=PANEL1_PASSWORD, name="EMO SMS",
)
panel2 = PanelSession(
    base=PANEL2_BASE, login_page=PANEL2_LOGIN_PAGE, signin_url=PANEL2_SIGNIN_URL,
    cdr_url=PANEL2_CDR_URL, data_url=PANEL2_DATA_URL,
    username=PANEL2_USERNAME, password=PANEL2_PASSWORD, name="PROTON",
)
panel3 = PanelSession(
    base=PANEL3_BASE, login_page=PANEL3_LOGIN_PAGE, signin_url=PANEL3_SIGNIN_URL,
    cdr_url=PANEL3_CDR_URL, data_url=PANEL3_DATA_URL,
    username=PANEL3_USERNAME, password=PANEL3_PASSWORD, name="konekta",
)
panel4 = PanelSession(
    base=PANEL4_BASE, login_page=PANEL4_LOGIN_PAGE, signin_url=PANEL4_SIGNIN_URL,
    cdr_url=PANEL4_CDR_URL, data_url=PANEL4_DATA_URL,
    username=PANEL4_USERNAME, password=PANEL4_PASSWORD, name="GREEN",
)
panel5 = PanelSession(
    base=PANEL5_BASE, login_page=PANEL5_LOGIN_PAGE, signin_url=PANEL5_SIGNIN_URL,
    cdr_url=PANEL5_CDR_URL, data_url=PANEL5_DATA_URL,
    username=PANEL5_USERNAME, password=PANEL5_PASSWORD, name="LAMIX",
)
PANELS = [panel, panel2, panel3, panel4, panel5]

# ══════════════════════════════════════════════════════════════
#                   WORKER FUNCTIONS
# ══════════════════════════════════════════════════════════════

async def _watch_membership(app, user_id):
    await asyncio.sleep(60)
    try:
        statuses = await check_membership_per_channel(app.bot, user_id)
        if not all(statuses.values()):
            try:
                await app.bot.send_message(
                    chat_id=user_id, text=JOIN_TEXT,
                    parse_mode=ParseMode.HTML,
                    reply_markup=join_gate_markup(statuses),
                    disable_web_page_preview=True,
                )
            except Exception:
                pass
    except Exception:
        pass

async def _panel_worker(app, p, wi_logged, wi_login, wi_last_login):
    last_reset_day = datetime.now().day
    while True:
        try:
            today = datetime.now().day
            if today != last_reset_day:
                worker_info["otps_today"] = 0
                last_reset_day = today

            if not p._logged_in:
                worker_info[wi_logged] = False
                if not p._can_attempt_login():
                    wait = p._login_backoff - (time.time() - p._last_login_try)
                    await asyncio.sleep(min(max(wait, 1), POLL_INTERVAL))
                    continue
                ok = await p.login()
                if not ok:
                    worker_info[wi_login] = worker_info.get(wi_login, 0) + 1
                    if worker_info[wi_login] <= 2:
                        await notify_admins(app, f"┌─ [{p._name}]\n├─❏ ʟᴏɢɪɴ ꜰᴀɪʟᴇᴅ\n└─❏ ʀᴇᴛʀʏ ɪɴ {p._login_backoff}s")
                    await asyncio.sleep(POLL_INTERVAL)
                    continue

                worker_info[wi_logged]     = True
                worker_info[wi_login]      = 0
                worker_info[wi_last_login] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                await notify_admins(app, f"┌─ [{p._name}]\n├─❏ ʟᴏɢɪɴ ᴏᴋ\n└─❏ ʟɪᴠᴇ")

                startup_rows, _ = await p.fetch_cdr()
                if startup_rows:
                    for r in startup_rows:
                        if not r.get("number") or not r.get("sms"):
                            continue
                        h = hashlib.md5(f"{r['date']}{r['number']}{r['sms']}".encode()).hexdigest()
                        otp_cache.add(h)
                    logger.info(f"[{p._name}] Seeded {len(startup_rows)} rows into cache")
                continue

            await p._keepalive_ping()
            if not p._logged_in:
                continue

            rows, err = await p.fetch_cdr()

            if err in ("session_expired", "not_logged_in"):
                worker_info[wi_logged] = False
                p._logged_in           = False
                await notify_admins(app, f"┌─ [{p._name}]\n├─❏ ꜱᴇꜱꜱɪᴏɴ ᴇxᴘɪʀᴇᴅ\n└─❏ ʀᴇʟᴏɢɢɪɴɢ...")
                await asyncio.sleep(5)
                continue

            if err:
                logger.warning(f"[{p._name}] fetch_cdr error: {err}")
                await asyncio.sleep(POLL_INTERVAL)
                continue

            if rows:
                logger.info(f"[{p._name}] Fetched {len(rows)} rows")
                for row in rows:
                    try:
                        sms    = row.get("sms", "").strip()
                        number = row.get("number", "").strip()
                        date   = row.get("date", "").strip()
                        if not sms or not number:
                            continue
                        clean_num = re.sub(r"\D", "", number)
                        if not clean_num or len(clean_num) < 5:
                            continue
                        otp = extract_otp(sms)
                        if not otp:
                            logger.debug(f"[{p._name}] No OTP: {sms[:50]}")
                            continue
                        h = hashlib.md5(f"{date}{number}{sms}".encode()).hexdigest()
                        if h in otp_cache:
                            continue
                        existing = await db_fetchone("SELECT id FROM otp_history WHERE hash=$1", h)
                        if existing:
                            otp_cache.add(h)
                            continue
                        logger.info(f"[{p._name}] NEW OTP {mask_number(number)} | {otp}")
                        text_msg, markup = format_otp_message(row, otp, panel_name=p._name)
                        await app.bot.send_message(
                            chat_id=OTP_GROUP_ID, text=text_msg,
                            parse_mode=ParseMode.HTML, reply_markup=markup,
                            disable_web_page_preview=True,
                        )
                        otp_cache.add(h)
                        await db_execute(
                            "INSERT INTO otp_history (hash,number,otp,service,sms,range_name) VALUES ($1,$2,$3,$4,$5,$6) ON CONFLICT (hash) DO NOTHING",
                            h, number, otp, row.get("service", ""), sms, row.get("range", ""),
                        )
                        await db_execute(
                            "INSERT INTO traffic (range_name,number,sms,otp,service,received_at) VALUES ($1,$2,$3,$4,$5,$6)",
                            row.get("range", ""), number, sms, otp, row.get("service", ""), date,
                        )
                        worker_info["last_otp"]    = datetime.now().strftime("%H:%M:%S")
                        worker_info["otps_today"] += 1
                        await asyncio.sleep(0.3)
                    except Exception as re_:
                        logger.error(f"[{p._name}] Row error: {re_}", exc_info=True)
            else:
                logger.debug(f"[{p._name}] No new rows")

            if len(otp_cache) > 50000:
                otp_cache.clear()
                recent = await db_fetchall("SELECT hash FROM otp_history ORDER BY id DESC LIMIT 30000")
                for r in recent:
                    otp_cache.add(r["hash"])

            await asyncio.sleep(POLL_INTERVAL)

        except asyncio.CancelledError:
            break
        except Exception as e:
            worker_info["errors"] = worker_info.get("errors", 0) + 1
            logger.error(f"[{p._name}] Worker error: {e}", exc_info=True)
            await asyncio.sleep(15)

async def sms_worker(app):
    if worker_info["running"]:
        return
    worker_info["running"] = True
    await asyncio.gather(
        _panel_worker(app, panel,  "logged_in",    "login_errors",    "last_login"),
        _panel_worker(app, panel2, "logged_in_p2", "login_errors_p2", "last_login_p2"),
        _panel_worker(app, panel3, "logged_in_p3", "login_errors_p3", "last_login_p3"),
        _panel_worker(app, panel4, "logged_in_p4", "login_errors_p4", "last_login_p4"),
        _panel_worker(app, panel5, "logged_in_p5", "login_errors_p5", "last_login_p5"),
    )
    worker_info["running"] = False

JOIN_TEXT    = f"┌─ {BOT_NAME}\n├─❏ ᴊᴏɪɴ ᴀʟʟ ᴄʜᴀɴɴᴇʟꜱ ᴛᴏ ᴄᴏɴᴛɪɴᴜᴇ\n└─❏ ᴛᴀᴘ ᴠᴇʀɪꜰʏ ᴡʜᴇɴ ᴅᴏɴᴇ"
WELCOME_TEXT = f"┌─ {BOT_NAME}\n├─❏ ʟɪᴠᴇ ᴏᴛᴘ ᴍᴏɴɪᴛᴏʀɪɴɢ 24/7\n└─❏"
ADMIN_TEXT   = f"┌─ {BOT_NAME}\n├─❏ ᴡᴇʟᴄᴏᴍᴇ ʙᴀᴄᴋ, ᴀᴅᴍɪɴ\n└─❏"
GET_NUM_TEXT = f"┌─ ɢᴇᴛ ɴᴜᴍʙᴇʀ\n├─❏ ꜱᴇʟᴇᴄᴛ ꜱᴇʀᴠɪᴄᴇ\n└─❏"

# ══════════════════════════════════════════════════════════════
#                   HANDLERS
# ══════════════════════════════════════════════════════════════

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await register_user(user)
    if await is_banned_user(user.id):
        await send_msg(context.bot, update.effective_chat.id, "ʏᴏᴜ ʜᴀᴠᴇ ʙᴇᴇɴ ʙᴀɴɴᴇᴅ.")
        return
    if not is_admin(user.id):
        if is_flooded(user.id):
            await send_msg(context.bot, update.effective_chat.id, "ꜱʟᴏᴡ ᴅᴏᴡɴ.")
            return
        if maintenance:
            await send_msg(context.bot, update.effective_chat.id, "ʙᴏᴛ ᴜɴᴅᴇʀ ᴍᴀɪɴᴛᴇɴᴀɴᴄᴇ.")
            return
    statuses   = await check_membership_per_channel(context.bot, user.id)
    all_joined = all(statuses.values())
    if not all_joined:
        await send_msg(context.bot, update.effective_chat.id, JOIN_TEXT, reply_markup=join_gate_markup(statuses))
        return
    welcome = ADMIN_TEXT if is_admin(user.id) else WELCOME_TEXT
    await context.bot.send_message(chat_id=update.effective_chat.id, text=".", reply_markup=ReplyKeyboardRemove())
    await send_msg(context.bot, update.effective_chat.id, welcome, reply_markup=main_menu_markup(user.id))
    asyncio.create_task(_watch_membership(context.application, user.id))

async def cancel_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    USER_STATE.pop(update.effective_user.id, None)
    await send_msg(context.bot, update.effective_chat.id, "ᴄᴀɴᴄᴇʟʟᴇᴅ.", reply_markup=main_menu_markup(update.effective_user.id))

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user  = query.from_user
    data  = query.data
    await query.answer()

    if await is_banned_user(user.id) and data != "check_join":
        await query.answer("ʙᴀɴɴᴇᴅ.", show_alert=True)
        return

    if data == "check_join":
        statuses = await check_membership_per_channel(context.bot, user.id)
        if all(statuses.values()):
            await register_user(user)
            welcome = ADMIN_TEXT if is_admin(user.id) else WELCOME_TEXT
            await edit_msg(query, welcome, reply_markup=main_menu_markup(user.id))
            asyncio.create_task(_watch_membership(context.application, user.id))
        else:
            await edit_msg(query, JOIN_TEXT, reply_markup=join_gate_markup(statuses))
            await query.answer("ᴊᴏɪɴ ᴀʟʟ ᴄʜᴀɴɴᴇʟꜱ ꜰɪʀꜱᴛ.", show_alert=True)
        return

    if data.startswith("noop_joined__"):
        await query.answer("ᴀʟʀᴇᴀᴅʏ ᴊᴏɪɴᴇᴅ.", show_alert=False)
        return

    if data == "menu_back":
        statuses = await check_membership_per_channel(context.bot, user.id)
        if not all(statuses.values()):
            await edit_msg(query, JOIN_TEXT, reply_markup=join_gate_markup(statuses))
            return
        welcome = ADMIN_TEXT if is_admin(user.id) else WELCOME_TEXT
        await edit_msg(query, welcome, reply_markup=main_menu_markup(user.id))
        return

    if data == "menu_admin":
        if not is_admin(user.id):
            await query.answer("ᴀᴅᴍɪɴꜱ ᴏɴʟʏ.", show_alert=True)
            return
        await edit_msg(query, admin_text(), reply_markup=admin_markup())
        return

    if data == "menu_live_traffic":
        total  = await db_fetchval("SELECT COUNT(*) FROM traffic") or 0
        recent = await db_fetchall("SELECT number, service, otp, received_at FROM traffic ORDER BY id DESC LIMIT 5")
        lines  = []
        for r in recent:
            svc_emoji, svc_short = get_service_info(r["service"] or "")
            lines.append(f"├─❏ {svc_emoji} {mask_number(r['number'])} — <code>{r['otp']}</code>")
        body   = "\n".join(lines) if lines else "├─❏ ɴᴏ ʀᴇᴄᴇɴᴛ ᴛʀᴀꜰꜰɪᴄ"
        await edit_msg(query, f"┌─ ʟɪᴠᴇ ᴛʀᴀꜰꜰɪᴄ\n├─❏ ᴛᴏᴛᴀʟ ᴏᴛᴘꜱ : {total}\n{body}\n└─❏", reply_markup=back_to_menu())
        return

    if data == "menu_get_number":
        statuses = await check_membership_per_channel(context.bot, user.id)
        if not all(statuses.values()):
            await edit_msg(query, JOIN_TEXT, reply_markup=join_gate_markup(statuses))
            return
        if not is_admin(user.id) and maintenance:
            await query.answer("ᴍᴀɪɴᴛᴇɴᴀɴᴄᴇ.", show_alert=True)
            return
        _, markup = await build_service_grid()
        if markup is None:
            await edit_msg(query, "┌─ ɴᴜᴍʙᴇʀꜱ\n├─❏ ɴᴏ ɴᴜᴍʙᴇʀꜱ ᴀᴠᴀɪʟᴀʙʟᴇ\n└─❏", reply_markup=back_to_menu())
            return
        await edit_msg(query, GET_NUM_TEXT, reply_markup=markup)
        return

    if data.startswith("gns__"):
        service  = data[5:]
        _, markup = await build_country_grid(service)
        if markup is None:
            await query.answer("ɴᴏ ɴᴜᴍʙᴇʀꜱ.", show_alert=True)
            return
        emoji, _ = get_service_info(service)
        await edit_msg(query, f"┌─ ɢᴇᴛ ɴᴜᴍʙᴇʀ\n├─❏ {emoji} ꜱᴇʀᴠɪᴄᴇ : {sc(service)}\n├─❏ ꜱᴇʟᴇᴄᴛ ᴄᴏᴜɴᴛʀʏ\n└─❏", reply_markup=markup)
        return

    if data.startswith("gnc__"):
        parts   = data[5:].split("__", 1)
        country = parts[0]
        service = parts[1] if len(parts) > 1 else "All"
        wait    = await check_number_cooldown(user.id)
        if wait > 0 and not is_admin(user.id):
            await query.answer(f"ᴡᴀɪᴛ {wait}s.", show_alert=True)
            return
        pool = await get_pool()
        async with pool.acquire() as conn:
            async with conn.transaction():
                row = await conn.fetchrow(
                    "SELECT id, number, flag FROM numbers WHERE country=$1 AND service=$2 AND is_used=FALSE LIMIT 1 FOR UPDATE SKIP LOCKED",
                    country, service,
                )
                if not row:
                    await query.answer("ɴᴏ ɴᴜᴍʙᴇʀꜱ ᴀᴠᴀɪʟᴀʙʟᴇ.", show_alert=True)
                    return
                await conn.execute(
                    "UPDATE numbers SET is_used=TRUE, used_by=$1, use_date=NOW() WHERE id=$2",
                    user.id, row["id"],
                )
                num_id = row["id"]
                number = row["number"]
                flag   = row["flag"] or ""
        if not is_admin(user.id):
            await set_number_cooldown(user.id)
        await edit_msg(query, number_display_text(number, country, flag, service), reply_markup=number_assigned_markup(country, service, num_id))
        return

    if data.startswith("chgn__"):
        parts = data.split("__")
        if len(parts) < 4:
            await query.answer("ɪɴᴠᴀʟɪᴅ.", show_alert=True)
            return
        old_id  = parts[-1]
        service = parts[-2]
        country = "__".join(parts[1:-2])
        wait    = await check_number_cooldown(user.id)
        if wait > 0 and not is_admin(user.id):
            await query.answer(f"ᴡᴀɪᴛ {wait}s.", show_alert=True)
            return
        if old_id.isdigit():
            await db_execute(
                "UPDATE numbers SET is_used=FALSE, used_by=NULL, use_date=NULL WHERE id=$1 AND used_by=$2",
                int(old_id), user.id,
            )
        pool = await get_pool()
        async with pool.acquire() as conn:
            async with conn.transaction():
                row = await conn.fetchrow(
                    "SELECT id, number, flag FROM numbers WHERE country=$1 AND service=$2 AND is_used=FALSE LIMIT 1 FOR UPDATE SKIP LOCKED",
                    country, service,
                )
                if not row:
                    await query.answer("ɴᴏ ᴍᴏʀᴇ ɴᴜᴍʙᴇʀꜱ.", show_alert=True)
                    return
                await conn.execute(
                    "UPDATE numbers SET is_used=TRUE, used_by=$1, use_date=NOW() WHERE id=$2",
                    user.id, row["id"],
                )
                num_id = row["id"]
                number = row["number"]
                flag   = row["flag"] or ""
        if not is_admin(user.id):
            await set_number_cooldown(user.id)
        await edit_msg(query, number_changed_text(number, country, flag, service), reply_markup=number_assigned_markup(country, service, num_id))
        return

    if not is_admin(user.id):
        return

    if data == "adm_back":
        USER_STATE.pop(user.id, None)
        await edit_msg(query, admin_text(), reply_markup=admin_markup())
        return

    if data == "adm_cancel_state":
        USER_STATE.pop(user.id, None)
        await edit_msg(query, "ᴄᴀɴᴄᴇʟʟᴇᴅ.", reply_markup=admin_markup())
        return

    if data == "adm_status":
        await edit_msg(query, await status_text(), reply_markup=back_to_admin())
        return

    if data == "adm_add_numbers":
        USER_STATE[user.id] = "ADM_PICK_SERVICE"
        await edit_msg(query, "┌─ ᴀᴅᴅ ɴᴜᴍʙᴇʀꜱ\n├─❏ ꜱᴇʟᴇᴄᴛ ꜱᴇʀᴠɪᴄᴇ\n└─❏", reply_markup=service_picker_markup())
        return

    if data == "adm_delete_numbers":
        _, markup = await build_delete_service_grid()
        if markup is None:
            await edit_msg(query, "┌─ ᴅᴇʟᴇᴛᴇ\n├─❏ ɴᴏ ɴᴜᴍʙᴇʀꜱ\n└─❏", reply_markup=back_to_admin())
            return
        await edit_msg(query, "┌─ ᴅᴇʟᴇᴛᴇ ɴᴜᴍʙᴇʀꜱ\n├─❏ ꜱᴇʟᴇᴄᴛ ꜱᴇʀᴠɪᴄᴇ\n└─❏", reply_markup=markup)
        return

    if data.startswith("del_svc__"):
        service  = data[9:]
        _, markup = await build_delete_country_grid(service)
        if markup is None:
            await query.answer("ɴᴏᴛʜɪɴɢ.", show_alert=True)
            return
        svc_label = sc(service) if service != "ALL" else "ᴀʟʟ"
        await edit_msg(query, f"┌─ ᴅᴇʟᴇᴛᴇ\n├─❏ ꜱᴇʀᴠɪᴄᴇ : {svc_label}\n├─❏ ꜱᴇʟᴇᴄᴛ ᴄᴏᴜɴᴛʀʏ\n└─❏", reply_markup=markup)
        return

    if data.startswith("del_cntry__"):
        parts   = data[11:].split("__", 1)
        service = parts[0]
        country = parts[1] if len(parts) > 1 else "ALL"
        if service == "ALL" and country == "ALL":
            deleted = await db_fetchval("SELECT COUNT(*) FROM numbers")
            await db_execute("DELETE FROM numbers")
        elif service == "ALL":
            deleted = await db_fetchval("SELECT COUNT(*) FROM numbers WHERE country=$1", country)
            await db_execute("DELETE FROM numbers WHERE country=$1", country)
        elif country == "ALL":
            deleted = await db_fetchval("SELECT COUNT(*) FROM numbers WHERE service=$1", service)
            await db_execute("DELETE FROM numbers WHERE service=$1", service)
        else:
            deleted = await db_fetchval("SELECT COUNT(*) FROM numbers WHERE country=$1 AND service=$2", country, service)
            await db_execute("DELETE FROM numbers WHERE country=$1 AND service=$2", country, service)
        svc_label     = sc(service) if service != "ALL" else "ᴀʟʟ"
        country_label = sc(country) if country != "ALL" else "ᴀʟʟ"
        await edit_msg(query,
            f"┌─ ᴅᴇʟᴇᴛᴇᴅ\n├─❏ ꜱᴇʀᴠɪᴄᴇ : {svc_label}\n├─❏ ᴄᴏᴜɴᴛʀʏ : {country_label}\n├─❏ ʀᴇᴍᴏᴠᴇᴅ : {deleted}\n└─❏",
            reply_markup=back_to_admin())
        return

    if data.startswith("adm_svc__"):
        service = data[9:]
        USER_STATE[user.id] = f"ADM_PICK_METHOD__{service}"
        emoji, _ = get_service_info(service)
        await edit_msg(query, f"┌─ ᴀᴅᴅ ɴᴜᴍʙᴇʀꜱ\n├─❏ {emoji} ꜱᴇʀᴠɪᴄᴇ : {sc(service)}\n├─❏ ᴄʜᴏᴏꜱᴇ ᴍᴇᴛʜᴏᴅ\n└─❏", reply_markup=method_picker_markup())
        return

    if data == "adm_svc_custom":
        USER_STATE[user.id] = "ADM_CUSTOM_SVC"
        await edit_msg(query, "┌─ ᴄᴜꜱᴛᴏᴍ ꜱᴇʀᴠɪᴄᴇ\n├─❏ ꜱᴇɴᴅ ꜱᴇʀᴠɪᴄᴇ ɴᴀᴍᴇ\n└─❏", reply_markup=cancel_state_markup("adm_add_numbers"))
        return

    if data == "adm_addmethod_file":
        state = USER_STATE.get(user.id, "")
        if state.startswith("ADM_PICK_METHOD__"):
            service = state[17:]
            USER_STATE[user.id] = f"WAITING_FILE__{service}"
            emoji, _ = get_service_info(service)
            await send_msg(context.bot, user.id,
                f"┌─ ᴀᴅᴅ ɴᴜᴍʙᴇʀꜱ\n├─❏ {emoji} ꜱᴇʀᴠɪᴄᴇ : {sc(service)}\n├─❏ ꜱᴇɴᴅ ꜰɪʟᴇ (.ᴛxᴛ .ᴄꜱᴠ .xʟꜱx .xʟꜱ)\n└─❏",
                reply_markup=cancel_state_markup("adm_add_numbers"))
        return

    if data == "adm_addmethod_type":
        state = USER_STATE.get(user.id, "")
        if state.startswith("ADM_PICK_METHOD__"):
            service = state[17:]
            USER_STATE[user.id] = f"TYPING_NUMBERS__{service}"
            emoji, _ = get_service_info(service)
            await send_msg(context.bot, user.id,
                f"┌─ ᴀᴅᴅ ɴᴜᴍʙᴇʀꜱ\n├─❏ {emoji} ꜱᴇʀᴠɪᴄᴇ : {sc(service)}\n├─❏ ꜱᴇɴᴅ ɴᴜᴍʙᴇʀꜱ, ᴏɴᴇ ᴘᴇʀ ʟɪɴᴇ\n└─❏",
                reply_markup=cancel_state_markup("adm_add_numbers"))
        return

async def _insert_numbers_bulk(service: str, result: dict):
    total_added = 0
    total_dupes = 0
    by_country  = {}
    pool = await get_pool()
    async with pool.acquire() as conn:
        for iso, v in result["groups"].items():
            country   = v["name"]
            flag      = v["flag"]
            added_for = []
            for num in v["numbers"]:
                r = await conn.execute(
                    "INSERT INTO numbers (country,flag,number,service) VALUES ($1,$2,$3,$4) ON CONFLICT (number) DO NOTHING",
                    country, flag, num, service,
                )
                if r == "INSERT 0 1":
                    total_added += 1
                    added_for.append(num)
                else:
                    total_dupes += 1
            if added_for:
                by_country[iso] = {"name": country, "flag": flag, "numbers": added_for}
        for num in result["unknown"]:
            r = await conn.execute(
                "INSERT INTO numbers (country,flag,number,service) VALUES ($1,$2,$3,$4) ON CONFLICT (number) DO NOTHING",
                "Unknown", "", num, service,
            )
            if r == "INSERT 0 1":
                total_added += 1
            else:
                total_dupes += 1
    return total_added, total_dupes, by_country

async def text_input_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    text = (update.message.text or "").strip()
    if not is_admin(user.id):
        if await is_banned_user(user.id):
            await send_msg(context.bot, update.effective_chat.id, "ʙᴀɴɴᴇᴅ.")
            return
        if is_flooded(user.id):
            await send_msg(context.bot, update.effective_chat.id, "ꜱʟᴏᴡ ᴅᴏᴡɴ.")
            return
        return
    state = USER_STATE.get(user.id)
    if not state:
        return
    if state == "ADM_CUSTOM_SVC":
        service = text.strip()
        USER_STATE[user.id] = f"ADM_PICK_METHOD__{service}"
        emoji, _ = get_service_info(service)
        await send_msg(context.bot, update.effective_chat.id,
            f"┌─ ᴀᴅᴅ ɴᴜᴍʙᴇʀꜱ\n├─❏ {emoji} ꜱᴇʀᴠɪᴄᴇ : {sc(service)}\n├─❏ ᴄʜᴏᴏꜱᴇ ᴍᴇᴛʜᴏᴅ\n└─❏",
            reply_markup=method_picker_markup())
        return
    if state.startswith("TYPING_NUMBERS__"):
        service    = state[16:]
        lines      = [re.sub(r"\D", "", line) for line in text.splitlines()]
        lines      = [n for n in lines if 7 <= len(n) <= 15]
        raw        = "\n".join(lines).encode("utf-8")
        loop       = asyncio.get_event_loop()
        result     = await loop.run_in_executor(None, extract_numbers_smart, raw, "numbers.txt")
        status_msg = await send_msg(context.bot, update.effective_chat.id, "⏳ ᴘʀᴏᴄᴇꜱꜱɪɴɢ...")
        total_added, total_dupes, by_country = await _insert_numbers_bulk(service, result)
        USER_STATE.pop(user.id, None)
        countries_summary = "\n".join(
            f"├─❏ {v['flag']} {sc(v['name'])} : {len(v['numbers'])}" for v in by_country.values()
        ) or "├─❏ ɴᴏ ᴄᴏᴜɴᴛʀɪᴇꜱ ᴅᴇᴛᴇᴄᴛᴇᴅ"
        emoji, _ = get_service_info(service)
        result_text = (
            f"┌─ ✅ ᴅᴏɴᴇ\n├─❏ {emoji} ꜱᴇʀᴠɪᴄᴇ : {sc(service)}\n"
            f"├─❏ ✅ ᴀᴅᴅᴇᴅ : {total_added}\n├─❏ ♻️ ᴅᴜᴘᴇꜱ : {total_dupes}\n"
            f"{countries_summary}\n└─❏"
        )
        try:
            await context.bot.edit_message_text(
                chat_id=update.effective_chat.id, message_id=status_msg.message_id,
                text=result_text, parse_mode=ParseMode.HTML,
                reply_markup=_markup([[_btn("ʙᴀᴄᴋ", cb="adm_back", style="danger")]]),
            )
        except Exception:
            await send_msg(context.bot, update.effective_chat.id, result_text,
                reply_markup=_markup([[_btn("ʙᴀᴄᴋ", cb="adm_back", style="danger")]]))
        for v in by_country.values():
            asyncio.create_task(broadcast_stock(context.application, v["name"], v["flag"], service, len(v["numbers"]), v["numbers"]))
        return

async def document_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not is_admin(user.id):
        return
    state = USER_STATE.get(user.id)
    if not state or not state.startswith("WAITING_FILE__"):
        return
    service    = state[14:]
    doc        = update.message.document
    name       = doc.file_name or "file.txt"
    ext        = name.lower().rsplit(".", 1)[-1]
    if ext not in ("txt", "csv", "xlsx", "xls"):
        await send_msg(context.bot, update.effective_chat.id, "⚠️ ɪɴᴠᴀʟɪᴅ ꜰɪʟᴇ. ᴜꜱᴇ .ᴛxᴛ .ᴄꜱᴠ .xʟꜱx .xʟꜱ")
        return
    status_msg = await send_msg(context.bot, update.effective_chat.id, "⏳ ᴘʀᴏᴄᴇꜱꜱɪɴɢ...")
    USER_STATE.pop(user.id, None)
    try:
        f       = await doc.get_file()
        content = bytes(await f.download_as_bytearray())
        loop    = asyncio.get_event_loop()
        result  = await loop.run_in_executor(None, extract_numbers_smart, content, name)
        total_added, total_dupes, by_country = await _insert_numbers_bulk(service, result)
        countries_summary = "\n".join(
            f"├─❏ {v['flag']} {sc(v['name'])} : {len(v['numbers'])}" for v in by_country.values()
        ) or "├─❏ ɴᴏ ᴄᴏᴜɴᴛʀɪᴇꜱ ᴅᴇᴛᴇᴄᴛᴇᴅ"
        emoji, _ = get_service_info(service)
        result_text = (
            f"┌─ ✅ ᴅᴏɴᴇ\n├─❏ {emoji} ꜱᴇʀᴠɪᴄᴇ : {sc(service)}\n├─❏ 📄 ꜰɪʟᴇ : {name}\n"
            f"├─❏ 📊 ᴛᴏᴛᴀʟ : {result['total']}\n├─❏ ✅ ᴀᴅᴅᴇᴅ : {total_added}\n"
            f"├─❏ ♻️ ᴅᴜᴘᴇꜱ : {total_dupes}\n{countries_summary}\n└─❏"
        )
        try:
            await context.bot.edit_message_text(
                chat_id=update.effective_chat.id, message_id=status_msg.message_id,
                text=result_text, parse_mode=ParseMode.HTML,
                reply_markup=_markup([[_btn("ʙᴀᴄᴋ", cb="adm_back", style="danger")]]),
            )
        except Exception:
            await send_msg(context.bot, update.effective_chat.id, result_text,
                reply_markup=_markup([[_btn("ʙᴀᴄᴋ", cb="adm_back", style="danger")]]))
        for v in by_country.values():
            asyncio.create_task(broadcast_stock(context.application, v["name"], v["flag"], service, len(v["numbers"]), v["numbers"]))
    except Exception as e:
        logger.error(f"Document handler: {e}")
        try:
            await context.bot.edit_message_text(
                chat_id=update.effective_chat.id, message_id=status_msg.message_id,
                text="❌ ᴇʀʀᴏʀ ᴘʀᴏᴄᴇꜱꜱɪɴɢ ꜰɪʟᴇ.", parse_mode=ParseMode.HTML,
                reply_markup=_markup([[_btn("ʙᴀᴄᴋ", cb="adm_back", style="danger")]]),
            )
        except Exception:
            pass

# ══════════════════════════════════════════════════════════════
#                HEALTH + STARTUP
# ══════════════════════════════════════════════════════════════

async def health_handler(request):
    return web.Response(
        text=json.dumps({
            "status":     "ok",
            "bot":        BOT_NAME,
            "worker":     worker_info["running"],
            "emo_sms":    "online" if worker_info["logged_in"]    else "offline",
            "proton":     "online" if worker_info["logged_in_p2"] else "offline",
            "konekta":    "online" if worker_info["logged_in_p3"] else "offline",
            "green":      "online" if worker_info["logged_in_p4"] else "offline",
            "lamix":      "online" if worker_info["logged_in_p5"] else "offline",
            "otps_today": worker_info["otps_today"],
            "last_otp":   worker_info["last_otp"],
        }),
        content_type="application/json",
        status=200,
    )

_web_runner = None

async def post_init(application):
    global maintenance, _web_runner
    await init_db()
    if await get_setting("maintenance") == "1":
        maintenance = True
    extra = await get_setting("extra_admins")
    if extra:
        for eid in extra.split(","):
            eid = eid.strip()
            if eid.isdigit():
                aid = int(eid)
                if aid not in ADMIN_IDS:
                    ADMIN_IDS.append(aid)
    recent = await db_fetchall("SELECT hash FROM otp_history ORDER BY id DESC LIMIT 30000")
    for r in recent:
        otp_cache.add(r["hash"])
    logger.info(f"OTP cache seeded: {len(otp_cache)} hashes")
    await application.bot.set_my_commands([
        BotCommand("start",  "start"),
        BotCommand("cancel", "cancel"),
    ])
    # ── Web server for Railway health check ──
    app_web = web.Application()
    app_web.router.add_get("/",       health_handler)
    app_web.router.add_get("/health", health_handler)
    _web_runner = web.AppRunner(app_web)
    await _web_runner.setup()
    site = web.TCPSite(_web_runner, "0.0.0.0", PORT)
    await site.start()
    logger.info(f"Health server on :{PORT}")
    # ── Start SMS worker ──
    asyncio.get_event_loop().create_task(sms_worker(application))
    logger.info(f"{BOT_NAME} live on Railway")

async def post_shutdown(application):
    global _web_runner
    logger.info("Shutting down...")
    for p in PANELS:
        try:
            await p.close()
        except Exception:
            pass
    if _web_runner:
        await _web_runner.cleanup()

# ══════════════════════════════════════════════════════════════
#                      MAIN ENTRY
# ══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    application = (
        ApplicationBuilder()
        .token(BOT_TOKEN)
        .post_init(post_init)
        .post_shutdown(post_shutdown)
        .build()
    )
    application.add_handler(CommandHandler("start",  start))
    application.add_handler(CommandHandler("cancel", cancel_cmd))
    application.add_handler(CallbackQueryHandler(handle_callback))
    application.add_handler(MessageHandler(filters.Document.ALL, document_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_input_handler))
    logger.info(f"Starting {BOT_NAME}...")
    application.run_polling(drop_pending_updates=True, allowed_updates=Update.ALL_TYPES)
