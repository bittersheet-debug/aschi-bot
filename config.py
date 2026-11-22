"""
ASCHI BOT — CONFIGURATION & CONSTANTS
ASCHEN EVENT ORGANIZER
Wedding Garden Aesthetic: White, Cream, Soft Gold Theme
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Base paths
BASE_DIR = Path(__file__).resolve().parent
ENV_PATH = BASE_DIR / ".env"

# Load environment variables
if ENV_PATH.exists():
    load_dotenv(dotenv_path=ENV_PATH)
else:
    load_dotenv()

# Bot Identity
BOT_NAME = "ASCHI BOT"
BOT_USERNAME = os.getenv("BOT_USERNAME", "@ASCHIASCHENBOT")
OFFICIAL_ORGANIZER = "@ASCHENEO"
OFFICIAL_CONTACT = "@FPENGAMAT"
CONTACT_URL = "https://t.me/FPENGAMAT"
ORDER_URL = "https://t.me/ASCHENEO"

# Telegram Bot Token & Owner ID
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
OWNER_ID = int(os.getenv("OWNER_ID", "0")) if os.getenv("OWNER_ID", "0").isdigit() else 0

# Database
if os.getenv("VERCEL"):
    import shutil
    vercel_db = Path("/tmp/aschi_bot.db")
    orig_db = BASE_DIR / "aschi_bot.db"
    if orig_db.exists() and not vercel_db.exists():
        try:
            shutil.copyfile(orig_db, vercel_db)
        except Exception:
            pass
    DB_PATH = str(vercel_db)
else:
    DB_PATH = os.getenv("DB_PATH", str(BASE_DIR / "aschi_bot.db"))

# Image Search APIs (Modular & Configurable)
UNSPLASH_ACCESS_KEY = os.getenv("UNSPLASH_ACCESS_KEY", "")
GOOGLE_CUSTOM_SEARCH_KEY = os.getenv("GOOGLE_CUSTOM_SEARCH_KEY", "")
GOOGLE_SEARCH_CX = os.getenv("GOOGLE_SEARCH_CX", "")

# Fallback Image: STRICTLY FOOD ONLY (never wedding/bride/venue photo!)
# High-resolution appetizing gourmet culinary food dish from Unsplash
IMAGE_NOT_FOUND_URL = "https://images.unsplash.com/photo-1546069901-ba9599a7e63c?auto=format&fit=crop&w=800&q=80"
IMAGE_NOT_FOUND_TEXT = "FOTO MAKANAN BELUM TERSEDIA."

# Aesthetic Decorators & Headers
HEADER_BORDER = "━━━━━━━━━━━━━━━━━━━━"
TITLE_DECOR = "𓄲  𓏼  @ASCHIASCHENBOT ➤ – ASCHI! 𝗔𝗦𝗖𝗛𝗘𝗡  𓈒   !"
FOOTER_DECOR = ".ᐟ ── જ⁀➴ ⓘ 𝗔𝗦𝗖𝗛𝗘𝗡  . @ASCHENEO"

# Default Order Button settings
DEFAULT_ORDER_BTN_1_TEXT = "ORDER VIA @ASCHENEO"
DEFAULT_ORDER_BTN_1_URL = "https://t.me/ASCHENEO"
DEFAULT_ORDER_BTN_2_TEXT = "ORDER VIA @ASCHENEO :: OFFICIAL"
DEFAULT_ORDER_BTN_2_URL = "https://t.me/ASCHENEO"
