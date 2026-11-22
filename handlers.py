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
from database import register_user, get_setting, get_food_by_command
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
    f"• <code>/Indonesia</code> — Daftar command Indonesian Food 🇮🇩\n"
    f"• <code>/Korean</code> — Daftar command Korean Food 🇰🇷\n"
    f"• <code>/Foreign</code> — Daftar command Foreign Food 🌎\n\n"
    f"<b>2. Command Langsung Makanan:</b>\n"
    f"Ketik command hidangan apa saja untuk langsung melihat foto dan tombol order:\n"
    f"• Contoh: <code>/telur</code>, <code>/rendang</code>, <code>/sate_ayam</code>, <code>/bulgogi</code>, <code>/pizza</code>, <code>/tiramisu</code>\n\n"
    f"<b>3. Layanan Wedding Menu:</b>\n"
    f"Konsultasi paket wedding planner resmi hubungi {OFFICIAL_CONTACT}.\n\n"
    f"<b>4. Perintah Moderasi Grup (Admin):</b>\n"
    f"• <code>/ban</code>, <code>/mute [durasi]</code>, <code>/kick</code>, <code>/unban</code>, <code>/unmute</code>\n\n"
    f"<b>5. Admin Settings:</b>\n"
    f"• <code>/maurits</code> — Pengaturan ASCHI BOT (Khusus Admin)\n\n"
    f"{FOOTER_DECOR}"
)

GROUP_MGMT_GUIDE = (
    f"{TITLE_DECOR}\n\n"
    f"🛡️ <b>GROUP MANAGEMENT SYSTEM</b>\n\n"
    f"ASCHI BOT siap menjaga ketertiban grup Telegram acara Anda.\n\n"
    f"<b>Persyaratan Administrator:</b>\n"
    f"Jadikan @ASCHIASCHENBOT sebagai Administrator grup dengan izin:\n"
    f"• Ban Users\n"
    f"• Restrict Members\n"
    f"• Delete Messages (opsional)\n\n"
    f"<b>Daftar Perintah Moderasi:</b>\n"
    f"• <code>/ban [alasan]</code> — Memblokir anggota (reply / ID)\n"
    f"• <code>/mute [10m/1h/1d]</code> — Membatasi pesan sesuai durasi\n"
    f"• <code>/kick [alasan]</code> — Mengeluarkan anggota dari grup\n"
    f"• <code>/unban [ID]</code> — Membuka blokir anggota\n"
    f"• <code>/unmute [ID]</code> — Mengembalikan izin pesan\n\n"
    f"<i>Seluruh tindakan moderasi dicatat otomatis ke database activity logs.</i>\n\n"
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
    "/start", "/help", "/indonesia", "/korean", "/foreign", "/maurits",
    "/ban", "/mute", "/kick", "/unban", "/unmute", "/menu", "/menuaschi"
}


@router.message(F.text.startswith("/"))
async def dynamic_food_command_handler(message: Message):
    """
    Catches any food command starting with '/' (e.g. /telur, /rendang, /bulgogi, etc.)
    and immediately sends the photo, exact caption, and 2 order buttons.
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
        await send_food_item_card(
            bot=message.bot,
            chat_id=message.chat.id,
            food=food
        )
    else:
        await message.reply(
            f"Command <code>{raw_cmd}</code> tidak ditemukan.\n"
            f"Ketik <code>/Indonesia</code>, <code>/Korean</code>, atau <code>/Foreign</code> untuk melihat daftar command menu.",
            parse_mode="HTML"
        )
