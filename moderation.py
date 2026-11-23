"""
ASCHI BOT — GROUP MODERATION SYSTEM & WELCOME SYSTEM
ASCHEN EVENT ORGANIZER
Handles:
1. Mandatory Group Administrator verification and automatic permission checks.
2. The 5 core moderation commands: /ban, /unban, /mute, /unmute, /kick.
   - 3 Target resolution methods: @username, User ID, Reply to message.
   - Exact notification templates with @USERNAME and @ADMIN tags.
   - Inline [ UNMUTE ] button on muted notifications with authorized callback handler.
   - Specific error handling: Member Not Found, Invalid User ID, Target Not Found,
     Missing Admin Permission, Member Already Muted, Member Already Unmuted, Action Failed.
3. Automatic Group Welcome System:
   - Welcomes new members with exact ASCHEN template.
   - Auto-deletes bot's welcome message after 5 seconds (or configured duration).
   - Supports text, photo, gift (GIF), and video media.
"""

import os
import re
import time
import asyncio
import logging
from typing import Optional, Tuple
from aiogram import Router, F, Bot
from aiogram.types import (
    Message,
    CallbackQuery,
    ChatMemberUpdated,
    ChatPermissions,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from aiogram.filters import Command, ChatMemberUpdatedFilter, JOIN_TRANSITION, PROMOTED_TRANSITION
from aiogram.enums import ChatMemberStatus, ChatType

from database import (
    update_group_status,
    get_setting,
    register_user,
    DEFAULT_GROUP_WELCOME_TEXT,
)
from config import OWNER_ID

logger = logging.getLogger(__name__)
router = Router(name="moderation")

# In-memory deduplication for group welcome messages: {(chat_id, user_id): timestamp}
_welcomed_users = {}

# Exact notices for bot administrator status
NOTICE_NOT_ADMIN = (
    "「 ASCHI BOT — SYSTEM NOTICE 」\n\n"
    "Untuk mengaktifkan layanan moderasi ASCHI BOT, mohon jadikan bot sebagai Administrator grup terlebih dahulu.\n\n"
    "Pastikan bot mendapatkan izin:\n"
    "- Ban Users.\n"
    "- Restrict Members.\n"
    "- Delete Messages jika diperlukan.\n"
    "- Manage Chat jika diperlukan.\n\n"
    "Setelah selesai, sistem akan memeriksa kembali seluruh izin."
)

NOTICE_ACTIVATED = (
    "「 ASCHI BOT — SYSTEM ACTIVATED 」\n\n"
    "ASCHI BOT berhasil diaktifkan!\n\n"
    "Seluruh layanan yang memiliki izin telah tersedia dan siap digunakan.\n\n"
    "Thank you for using ASCHI BOT."
)

NOTICE_REVOKED = (
    "「 ASCHI BOT — SYSTEM NOTICE 」\n\n"
    "Izin Administrator ASCHI BOT telah dicabut atau dibatasi.\n"
    "Layanan moderasi dinonaktifkan sementara hingga izin dikembalikan.\n\n"
    "Mohon periksa kembali hak akses bot di pengaturan grup."
)


# ---------------- AUTOMATIC BOT PERMISSION CHECKER ----------------

@router.my_chat_member(ChatMemberUpdatedFilter(JOIN_TRANSITION))
async def handle_bot_join_group(event: ChatMemberUpdated):
    """Fired when ASCHI BOT is added to a group."""
    chat = event.chat
    new_member = event.new_chat_member

    is_admin = new_member.status in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.CREATOR]
    can_restrict = getattr(new_member, "can_restrict_members", False)
    can_delete = getattr(new_member, "can_delete_messages", False)

    await update_group_status(
        group_id=chat.id,
        title=chat.title or "Unknown Group",
        is_active=True,
        is_bot_admin=is_admin,
        can_restrict_members=can_restrict,
        can_delete_messages=can_delete
    )

    if not is_admin or not can_restrict:
        await event.bot.send_message(chat_id=chat.id, text=NOTICE_NOT_ADMIN)
    else:
        await event.bot.send_message(chat_id=chat.id, text=NOTICE_ACTIVATED)


@router.my_chat_member(ChatMemberUpdatedFilter(PROMOTED_TRANSITION))
async def handle_bot_promoted(event: ChatMemberUpdated):
    """Fired when ASCHI BOT is promoted to Administrator."""
    chat = event.chat
    new_member = event.new_chat_member

    can_restrict = getattr(new_member, "can_restrict_members", False)
    can_delete = getattr(new_member, "can_delete_messages", False)

    await update_group_status(
        group_id=chat.id,
        title=chat.title or "Unknown Group",
        is_active=True,
        is_bot_admin=True,
        can_restrict_members=can_restrict,
        can_delete_messages=can_delete
    )

    if can_restrict:
        await event.bot.send_message(chat_id=chat.id, text=NOTICE_ACTIVATED)
    else:
        await event.bot.send_message(chat_id=chat.id, text=NOTICE_NOT_ADMIN)


@router.my_chat_member()
async def handle_bot_member_update(event: ChatMemberUpdated):
    """Detects when bot permissions are modified or revoked."""
    chat = event.chat
    new_member = event.new_chat_member

    is_admin = new_member.status in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.CREATOR]
    can_restrict = getattr(new_member, "can_restrict_members", False)
    can_delete = getattr(new_member, "can_delete_messages", False)

    await update_group_status(
        group_id=chat.id,
        title=chat.title or "Unknown Group",
        is_active=new_member.status not in [ChatMemberStatus.LEFT, ChatMemberStatus.KICKED],
        is_bot_admin=is_admin,
        can_restrict_members=can_restrict,
        can_delete_messages=can_delete
    )

    if new_member.status in [ChatMemberStatus.MEMBER, ChatMemberStatus.RESTRICTED]:
        await event.bot.send_message(chat_id=chat.id, text=NOTICE_REVOKED)


# ---------------- AUTOMATIC GROUP WELCOME SYSTEM ----------------

def format_user_tag(user_id: int, username: Optional[str], full_name: Optional[str]) -> str:
    """Formats user identity: @username if available, otherwise display name."""
    if username:
        clean = username.lstrip("@").strip()
        return f"@{clean}"
    if full_name and full_name.strip():
        return full_name.strip()
    return f"User {user_id}"


async def trigger_group_welcome(bot: Bot, chat, user):
    """
    Sends automatic welcome message to new members in ASCHEN group.
    - Template with @USERNAME dynamic replacement
    - Supports Photo, GIF (Gift), Video, or text-only
    - Automatically deletes welcome message after 5 seconds (or configured duration)
    - Applies ONLY to the bot's welcome message
    """
    if user.is_bot:
        return

    # Track user in database
    await register_user(user.id, user.username, user.full_name)

    # Deduplication check (15s window per chat/user)
    now = time.time()
    dedup_key = (chat.id, user.id)
    if dedup_key in _welcomed_users and (now - _welcomed_users[dedup_key]) < 15:
        return
    _welcomed_users[dedup_key] = now

    # Periodic cleanup of dedup cache
    if len(_welcomed_users) > 500:
        expired = [k for k, v in _welcomed_users.items() if (now - v) > 60]
        for k in expired:
            _welcomed_users.pop(k, None)

    # Check if welcome is enabled
    if await get_setting("group_welcome_enabled", "1") != "1":
        return

    template = await get_setting("group_welcome_text", DEFAULT_GROUP_WELCOME_TEXT)
    media_type = await get_setting("group_welcome_media_type", "none")
    photo_id = await get_setting("group_welcome_photo_file_id", "")
    gift_id = await get_setting("group_welcome_gift_file_id", "")
    video_id = await get_setting("group_welcome_video_file_id", "")
    duration_str = await get_setting("group_welcome_duration", "5")

    try:
        duration = max(1, int(duration_str))
    except Exception:
        duration = 5

    user_tag = format_user_tag(user.id, user.username, user.full_name)
    welcome_text = template.replace("@USERNAME", user_tag)

    sent_msg = None
    try:
        if media_type == "photo" and photo_id:
            sent_msg = await bot.send_photo(chat_id=chat.id, photo=photo_id, caption=welcome_text)
        elif media_type == "gift" and gift_id:
            sent_msg = await bot.send_animation(chat_id=chat.id, animation=gift_id, caption=welcome_text)
        elif media_type == "video" and video_id:
            sent_msg = await bot.send_video(chat_id=chat.id, video=video_id, caption=welcome_text)
        else:
            sent_msg = await bot.send_message(chat_id=chat.id, text=welcome_text)
    except Exception as e:
        logger.error(f"Error sending group welcome message: {e}")
        return

    if sent_msg:
        async def _auto_delete_welcome(c_id: int, m_id: int, delay: int):
            try:
                await asyncio.sleep(delay)
                await bot.delete_message(chat_id=c_id, message_id=m_id)
            except Exception:
                pass

        if os.environ.get("VERCEL"):
            # Serverless execution: guarantee message deletion before invocation terminates
            await _auto_delete_welcome(chat.id, sent_msg.message_id, duration)
        else:
            asyncio.create_task(_auto_delete_welcome(chat.id, sent_msg.message_id, duration))


@router.chat_member(ChatMemberUpdatedFilter(JOIN_TRANSITION))
async def on_chat_member_join(event: ChatMemberUpdated):
    """Fired when a new member joins the group (supergroup transition)."""
    if event.chat.type in [ChatType.GROUP, ChatType.SUPERGROUP]:
        await trigger_group_welcome(event.bot, event.chat, event.new_chat_member.user)


@router.message(F.new_chat_members)
async def on_new_chat_members_message(message: Message):
    """Fired when new chat members message is received in group."""
    if message.chat.type in [ChatType.GROUP, ChatType.SUPERGROUP]:
        for member in message.new_chat_members:
            await trigger_group_welcome(message.bot, message.chat, member)
