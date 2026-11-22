"""
ASCHI BOT — VERCEL SERVERLESS WEBHOOK ENTRY POINT
ASCHEN EVENT ORGANIZER
Handles incoming Telegram Webhook updates on Vercel Serverless Functions.
"""

import os
import sys
import logging
from pathlib import Path

# Add project root to sys.path so modules can be imported seamlessly
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from fastapi import FastAPI, Request, Response, status
from fastapi.responses import JSONResponse, HTMLResponse
from aiogram import Bot, Dispatcher, types
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.memory import MemoryStorage

from config import BOT_TOKEN, BOT_NAME, BOT_USERNAME
from database import init_db
from seed_data import seed_database
import moderation
import food_menu
import admin_dashboard
import handlers

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("aschi_vercel")

# Initialize FastAPI
app = FastAPI(title="ASCHI BOT Vercel Webhook")

# Initialize Aiogram
bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)
dp = Dispatcher(storage=MemoryStorage())

# Include Routers
dp.include_router(moderation.router)
dp.include_router(food_menu.router)
dp.include_router(admin_dashboard.router)
dp.include_router(handlers.router)

_initialized = False


async def ensure_db_initialized():
    """Ensures database tables & food catalog are initialized once in container."""
    global _initialized
    if not _initialized:
        try:
            await init_db()
            await seed_database()
            _initialized = True
            logger.info("Database initialized successfully on Vercel.")
        except Exception as e:
            logger.error(f"Error initializing DB on Vercel: {e}", exc_info=True)


@app.get("/", response_class=HTMLResponse)
async def home_page(request: Request):
    """Informational landing page showing bot status and one-click webhook setup."""
    base_url = str(request.base_url).rstrip("/")
    webhook_target = f"{base_url}/api/webhook"
    set_webhook_url = f"{base_url}/api/set_webhook"

    return f"""
    <!DOCTYPE html>
    <html lang="id">
    <head>
        <meta charset="UTF-8">
        <title>{BOT_NAME} — Vercel Webhook Server</title>
        <style>
            body {{
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                background-color: #faf8f5;
                color: #333;
                display: flex;
                justify-content: center;
                align-items: center;
                min-height: 100vh;
                margin: 0;
            }}
            .card {{
                background: #ffffff;
                padding: 40px;
                border-radius: 16px;
                box-shadow: 0 10px 30px rgba(0,0,0,0.08);
                max-width: 600px;
                border-top: 6px solid #d4af37;
                text-align: center;
            }}
            h1 {{ color: #2c3e50; margin-bottom: 8px; }}
            p {{ color: #666; line-height: 1.6; }}
            .badge {{
                display: inline-block;
                padding: 6px 14px;
                background: #e8f5e9;
                color: #2e7d32;
                font-weight: bold;
                border-radius: 20px;
                margin-bottom: 20px;
            }}
            .code-box {{
                background: #f4f4f4;
                padding: 12px;
                border-radius: 8px;
                font-family: monospace;
                word-break: break-all;
                text-align: left;
                margin: 15px 0;
            }}
            .btn {{
                display: inline-block;
                background: #d4af37;
                color: white;
                text-decoration: none;
                padding: 12px 24px;
                border-radius: 8px;
                font-weight: bold;
                margin-top: 15px;
                transition: background 0.3s;
            }}
            .btn:hover {{ background: #c59b27; }}
        </style>
    </head>
    <body>
        <div class="card">
            <span class="badge">● ONLINE ON VERCEL</span>
            <h1>{BOT_NAME}</h1>
            <p><strong>ASCHEN EVENT ORGANIZER</strong> — Official Wedding & Group Management Bot</p>
            
            <p>Serverless webhook endpoint aktif dan siap menerima updates dari Telegram.</p>
            
            <div class="code-box">
                <strong>Webhook Target:</strong><br>{webhook_target}
            </div>

            <a href="{set_webhook_url}" class="btn">🚀 Aktifkan Webhook ke Telegram</a>
        </div>
    </body>
    </html>
    """


@app.post("/api/webhook")
async def telegram_webhook(request: Request):
    """Processes incoming Telegram updates via Webhook."""
    await ensure_db_initialized()
    try:
        data = await request.json()
        update = types.Update.model_validate(data, context={"bot": bot})
        await dp.feed_update(bot=bot, update=update)
        return {"ok": True}
    except Exception as e:
        logger.error(f"Error handling Telegram webhook update: {e}", exc_info=True)
        return JSONResponse(
            status_code=status.HTTP_200_OK,  # Always return 200 to Telegram so it doesn't repeatedly retry failed updates
            content={"ok": False, "error": str(e)}
        )


@app.get("/api/resync_photos")
async def resync_photos_endpoint():
    """Forces synchronization of all 87 authentic food photos and clears cached photo IDs."""
    try:
        await init_db()
        await seed_database()
        return {
            "success": True,
            "message": "All 87 menu & drink photos successfully resynchronized and photo_file_id cache cleared!"
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


@app.get("/api/set_webhook")
async def set_telegram_webhook(request: Request):
    """One-click setup endpoint to register the Vercel URL with Telegram API."""
    base_url = str(request.base_url).rstrip("/")
    # Force https if Vercel is behind SSL proxy
    if base_url.startswith("http://") and not "localhost" in base_url:
        base_url = base_url.replace("http://", "https://", 1)

    webhook_url = f"{base_url}/api/webhook"

    try:
        await bot.delete_webhook(drop_pending_updates=True)
        success = await bot.set_webhook(url=webhook_url, drop_pending_updates=True)
        return {
            "success": success,
            "message": "Webhook successfully registered to Telegram!",
            "webhook_url": webhook_url,
            "bot": BOT_USERNAME
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


@app.get("/api/delete_webhook")
async def delete_telegram_webhook():
    """Removes the webhook from Telegram (useful when switching back to local polling)."""
    try:
        success = await bot.delete_webhook(drop_pending_updates=True)
        return {
            "success": success,
            "message": "Webhook deleted. You can now use local polling."
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }
