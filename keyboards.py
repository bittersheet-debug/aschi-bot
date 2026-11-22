"""
ASCHI BOT — INLINE KEYBOARDS & NAVIGATION
ASCHEN EVENT ORGANIZER
Strict Compliance with PROMPT FIX FINAL:
- Under each food photo: ONLY the Two Order Buttons in separate rows.
- ALL BACK, NEXT, HOME, and other navigation buttons REMOVED from food photo view.
- Admin dashboard keyboards for /maurits preserved.
"""

from typing import List, Dict, Any, Optional
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from database import is_admin_or_owner, get_setting
from config import CONTACT_URL, ORDER_URL


def build_start_keyboard() -> InlineKeyboardMarkup:
    """
    Constructs the exact 3-button keyboard for /start:
    1. HELP
    2. CONTACT @FPENGAMAT (URL: https://t.me/FPENGAMAT)
    3. GROUP MANAGEMENT
    """
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📖 HELP", callback_data="nav:help")],
            [InlineKeyboardButton(text="✉️ CONTACT @FPENGAMAT", url=CONTACT_URL)],
            [InlineKeyboardButton(text="🛡️ GROUP MANAGEMENT", callback_data="nav:group_mgmt")],
        ]
    )


async def build_food_order_keyboard() -> InlineKeyboardMarkup:
    """
    Constructs ONLY the Two Order Buttons in separate rows:
    BUTTON 1: ORDER VIA @ASCHENEO
    BUTTON 2: ORDER VIA @ASCHENEO :: OFFICIAL
    Strictly NO BACK, NO NEXT, NO HOME, NO navigation buttons!
    """
    btn1_text = await get_setting("order_btn_1_text", "ORDER VIA @ASCHENEO")
    btn1_url = await get_setting("order_btn_1_url", ORDER_URL)
    btn2_text = await get_setting("order_btn_2_text", "ORDER VIA @ASCHENEO :: OFFICIAL")
    btn2_url = await get_setting("order_btn_2_url", ORDER_URL)

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=btn1_text, url=btn1_url)],
            [InlineKeyboardButton(text=btn2_text, url=btn2_url)],
        ]
    )


# ---------------- ADMIN KEYBOARDS (/maurits) ----------------
def build_admin_dashboard_keyboard() -> InlineKeyboardMarkup:
    """Main Admin Dashboard Navigation for /maurits."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📝 A. Welcome Settings", callback_data="admin_welcome:root")],
            [InlineKeyboardButton(text="🍽️ B. Menu & Wedding Settings", callback_data="admin_menu:root")],
            [InlineKeyboardButton(text="🍲 C. Food Management (Add/Edit)", callback_data="admin_food:root")],
            [InlineKeyboardButton(text="🖼️ D. Food Photo Settings", callback_data="admin_img:root")],
            [InlineKeyboardButton(text="💬 E. Caption Settings", callback_data="admin_caption:root")],
            [InlineKeyboardButton(text="🛒 F. Order Button Settings", callback_data="admin_btn:root")],
            [InlineKeyboardButton(text="🛡️ G. Group Management Settings", callback_data="admin_mod:root")],
            [InlineKeyboardButton(text="⚙️ H. Bot Settings & Backup", callback_data="admin_bot:root")],
            [InlineKeyboardButton(text="👥 I. Admin Access Control", callback_data="admin_acc:root")],
            [InlineKeyboardButton(text="🏠 TUTUP DASHBOARD", callback_data="nav:home")],
        ]
    )


def build_admin_back_keyboard(parent_callback: str = "admin:main") -> InlineKeyboardMarkup:
    """Standard back button for admin screens."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔙 BACK", callback_data=parent_callback)],
            [InlineKeyboardButton(text="🏠 ADMIN HOME", callback_data="admin:main")],
        ]
    )


def build_cancel_keyboard(action_name: str = "Batal") -> InlineKeyboardMarkup:
    """Cancel button for FSM conversation states."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=f"❌ {action_name}", callback_data="fsm:cancel")]
        ]
    )
