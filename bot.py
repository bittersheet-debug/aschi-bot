"""
ASCHI BOT — MAIN APPLICATION ENTRY POINT
ASCHEN EVENT ORGANIZER
Official Telegram Wedding & Group Management Assistant
Strict Compliance with Master Prompt Fix
"""

import asyncio
import logging
import sys
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand, BotCommandScopeDefault

from config import BOT_TOKEN, BOT_NAME
from database import init_db
from seed_data import seed_database
import moderation
import food_menu
import admin_dashboard
import handlers

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("aschi_bot")


async def setup_bot_commands(bot: Bot):
    """Registers official bot commands list in the Telegram Menu (hides /maurits from public menu)."""
    commands = [
        BotCommand(command="start", description="Mulai ASCHI BOT"),
        BotCommand(command="help", description="Panduan & daftar command"),
        BotCommand(command="menu", description="Daftar katalog aktif"),
        BotCommand(command="indonesia", description="Katalog Indonesian Food 🇮🇩"),
        BotCommand(command="korean", description="Katalog Korean Food 🇰🇷"),
        BotCommand(command="foreign", description="Katalog Foreign Food 🌎"),
    ]
    try:
        await bot.set_my_commands(commands, scope=BotCommandScopeDefault())
        logger.info("Bot commands successfully registered to Telegram API.")
    except Exception as e:
        logger.warning(f"Could not register commands to Telegram: {e}")


async def main():
    logger.info(f"Initializing {BOT_NAME} — ASCHEN EVENT ORGANIZER...")

    if not BOT_TOKEN:
        logger.error("ERROR: BOT_TOKEN is not set in environment or .env file!")
        return

    # 1. Initialize SQLite Database & Migrations
    logger.info("Initializing database schema...")
    await init_db()

    # 2. Seed Initial Wedding Menu Items & Direct Commands
    logger.info("Checking & seeding wedding food items with direct commands...")
    await seed_database()

    # 3. Create Bot & Dispatcher instances
    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    dp = Dispatcher(storage=MemoryStorage())

    # 4. Include Routers
    dp.include_router(moderation.router)
    dp.include_router(food_menu.router)
    dp.include_router(admin_dashboard.router)
    dp.include_router(handlers.router)

    # 5. Set Telegram commands
    await setup_bot_commands(bot)

    # 6. Start Polling with Keep-Alive auto-reconnect
    max_retries = 999999
    retry_delay = 5
    while True:
        try:
            logger.info(f"{BOT_NAME} is ONLINE and ready to serve! Starting polling...")
            await bot.delete_webhook(drop_pending_updates=True)
            await dp.start_polling(bot, handle_signals=False)
            break
        except (KeyboardInterrupt, SystemExit):
            logger.info("Bot termination requested.")
            break
        except Exception as e:
            logger.error(f"Unexpected connection error in bot polling: {e}. Auto-reconnecting in {retry_delay}s...", exc_info=True)
            await asyncio.sleep(retry_delay)
    
    await bot.session.close()
    logger.info(f"{BOT_NAME} shutdown gracefully.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot terminated by user.")
