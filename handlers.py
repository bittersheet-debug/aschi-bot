"""
ASCHI BOT — GENERAL HANDLERS & NAVIGATION ROUTER
ASCHEN EVENT ORGANIZER
Strict Compliance with PROMPT FIX FINAL:
- /start in private chat displays ONLY Welcome and 3 buttons (HELP, CONTACT @FPENGAMAT, GROUP MANAGEMENT)
- No food categories or wedding menus on /start
- Dynamic food command dispatcher: /telur, /rendang, /bulgogi, etc.
- Direct execution sends pure food photo, exact caption, and 2 order buttons
"""

import logging
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandStart, Command
from aiogram.enums import ChatType

from config import (
    TITLE_DECOR,
    FOOTER_DECOR,
    OFFICIAL_ORGANIZER,
    OFFICIAL_CONTACT,
)
from database import register_user, get_setting, get_food_by_command, is_catalog_enabled
from keyboards import build_start_keyboard
from food_menu import send_food_item_card

logger = logging.getLogger(__name__)
router = Router(name="handlers")

WELCOME_TEXT = (
    "WELCOME TO ASCHI BOT\n\n"
    "Welcome to ASCHI BOT — Official Assistant of ASCHEN EVENT ORGANIZER.\n\n"
    "Thank you for using ASCHI BOT. Please select the service below."
)

HELP_TEXT = (
    f"{TITLE_DECOR}\n\n"
    f"📖 <b>PANDUAN & PETUNJUK PENGGUNAAN ASCHI BOT</b>\n"
    f"<i>Official Assistant of {OFFICIAL_ORGANIZER}</i>\n\n"
    f"<b>1. Navigasi Katalog Makanan:</b>\n"
    f"• <code>/menu</code> — Lihat katalog makanan yang sedang aktif\n"
    f"• <code>/Indonesia</code> — Katalog Indonesian Food 🇮🇩\n"
    f"• <code>/Korean</code> — Katalog Korean Food 🇰🇷\n"
    f"• <code>/Foreign</code> — Katalog Foreign Food 🌎\n\n"
    f"<b>2. Command Langsung Makanan:</b>\n"
    f"Ketik command hidangan apa saja untuk langsung melihat foto dan tombol order:\n"
    f"• Contoh: <code>/telur</code>, <code>/rendang</code>, <code>/sate_ayam</code>, <code>/bulgogi</code>, <code>/pizza</code>, <code>/tiramisu</code>\n\n"
    f"<b>3. Layanan Wedding Menu:</b>\n"
    f"Konsultasi paket wedding planner resmi hubungi {OFFICIAL_CONTACT}.\n\n"
    f"<b>4. Admin Settings:</b>\n"
    f"• <code>/maurits</code> — Pengaturan ASCHI BOT (Khusus Admin)\n"
    f"• <code>/setindonesia on|off</code> — Kontrol status katalog Indonesia\n"
    f"• <code>/setkorean on|off</code> — Kontrol status katalog Korea\n"
    f"• <code>/setforeign on|off</code> — Kontrol status katalog Foreign\n\n"
    f"{FOOTER_DECOR}"
)

GROUP_MGMT_GUIDE = (
    f"{TITLE_DECOR}\n\n"
    f"🛡️ <b>GROUP MANAGEMENT SYSTEM</b>\n\n"
    f"ASCHI BOT siap melayani kebutuhan acara di grup Telegram Anda.\n\n"
    f"<b>Fitur Utama:</b>\n"
    f"• Sambutan otomatis anggota baru (Welcome System)\n"
    f"• Pemesanan katering wedding & event\n"
    f"• Pengaturan katalog dinamis oleh Admin\n\n"
    f"Ketik <code>/menu</code> untuk melihat katalog hidangan aktif.\n\n"
    f"{FOOTER_DECOR}"
)


# ---------------- START COMMAND ----------------

@router.message(CommandStart())
async def cmd_start(message: Message):
    """
    Handles /START command in private chat.
    Strict Rule: Only displays Welcome & 3 buttons (HELP, CONTACT @FPENGAMAT, GROUP MANAGEMENT).
    Does NOT send Welcome automatically when added to groups.
    """
    if message.chat.type != ChatType.PRIVATE:
        return

    user = message.from_user
    await register_user(user.id, user.username, user.full_name)

    welcome_text = await get_setting("welcome_message", WELCOME_TEXT)
    await message.reply(welcome_text, reply_markup=build_start_keyboard())


@router.message(Command("help", ignore_case=True))
async def cmd_help(message: Message):
    """Handles /HELP."""
    await message.reply(HELP_TEXT, parse_mode="HTML")


# ---------------- CALLBACK NAVIGATION ----------------

@router.callback_query(F.data == "nav:home")
async def cb_nav_home(callback: CallbackQuery):
    """Returns to /start Welcome screen."""
    await callback.answer()
    welcome_text = await get_setting("welcome_message", WELCOME_TEXT)
    try:
        await callback.message.edit_text(welcome_text, reply_markup=build_start_keyboard())
    except Exception:
        await callback.message.answer(welcome_text, reply_markup=build_start_keyboard())


@router.callback_query(F.data == "nav:help")
async def cb_nav_help(callback: CallbackQuery):
    """Shows Help Center."""
    await callback.answer()
    try:
        await callback.message.edit_text(HELP_TEXT, reply_markup=build_start_keyboard(), parse_mode="HTML")
    except Exception:
        await callback.message.answer(HELP_TEXT, reply_markup=build_start_keyboard(), parse_mode="HTML")


@router.callback_query(F.data == "nav:group_mgmt")
async def cb_nav_group_mgmt(callback: CallbackQuery):
    """Shows group management information."""
    await callback.answer()
    try:
        await callback.message.edit_text(GROUP_MGMT_GUIDE, reply_markup=build_start_keyboard(), parse_mode="HTML")
    except Exception:
        await callback.message.answer(GROUP_MGMT_GUIDE, reply_markup=build_start_keyboard(), parse_mode="HTML")


# ---------------- DYNAMIC FOOD COMMAND DISPATCHER ----------------

SYSTEM_COMMANDS = {
    "/start", "/help", "/menu", "/menuaschi",
    "/indonesia", "/korean", "/foreign",
    "/setindonesia", "/setkorean", "/setforeign",
    "/maurits", "/adminaschi"
}


@router.message(F.text.startswith("/"))
async def dynamic_food_command_handler(message: Message):
    """
    Catches any food command starting with '/' (e.g. /telur, /rendang, /bulgogi, etc.)
    and immediately sends the photo, exact caption, and 2 order buttons.
    If the catalog is OFF, rejects with: 'Maaf, katalog ini sedang tidak tersedia.'
    """
    raw_cmd = message.text.split()[0].lower()
    if "@" in raw_cmd:
        raw_cmd = raw_cmd.split("@")[0]

    # Ignore recognized system commands
    if raw_cmd in SYSTEM_COMMANDS:
        return

    # Check if command belongs to a food in database
    food = await get_food_by_command(raw_cmd)
    if food:
        food_cat = food.get("category", "").lower()
        if not await is_catalog_enabled(food_cat):
            await message.reply("Maaf, katalog ini sedang tidak tersedia.")
            return

        await send_food_item_card(
            bot=message.bot,
            chat_id=message.chat.id,
            food=food
        )
    else:
        await message.reply(
            f"Command <code>{raw_cmd}</code> tidak ditemukan.\n"
            f"Ketik <code>/menu</code> untuk melihat daftar katalog yang sedang aktif.",
            parse_mode="HTML"
        )
