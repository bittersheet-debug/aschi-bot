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
    log_moderation,
    get_setting,
    set_member_muted,
    set_member_unmuted,
    is_member_muted,
    get_muted_record,
    register_user,
    get_user_by_username,
    get_user_by_id,
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


# ---------------- RESOLUTION & PERMISSION HELPERS ----------------

def format_user_tag(user_id: int, username: Optional[str], full_name: Optional[str]) -> str:
    """Formats user identity: @username if available, otherwise display name."""
    if username:
        clean = username.lstrip("@").strip()
        return f"@{clean}"
    if full_name and full_name.strip():
        return full_name.strip()
    return f"User {user_id}"


def get_admin_tag(user) -> str:
    """Returns formatted admin identity (@username or full name)."""
    if user.username:
        clean = user.username.lstrip("@").strip()
        return f"@{clean}"
    return user.full_name or f"Admin {user.id}"


async def check_admin_rights(message: Message) -> Tuple[bool, Optional[str]]:
    """
    Validates:
    1. Group/Supergroup context
    2. Bot is Administrator with can_restrict_members
    3. Caller is Group Administrator / Creator or OWNER_ID
    Returns (True, None) or (False, "Missing Admin Permission")
    """
    if message.chat.type not in [ChatType.GROUP, ChatType.SUPERGROUP]:
        return False, "Perintah moderasi hanya dapat digunakan di dalam Grup Telegram."

    # Verify bot rights
    try:
        bot_member = await message.chat.get_member(message.bot.id)
        if bot_member.status != ChatMemberStatus.ADMINISTRATOR or not getattr(bot_member, "can_restrict_members", False):
            return False, "Missing Admin Permission"
    except Exception:
        return False, "Missing Admin Permission"

    # Verify caller rights
    caller_id = message.from_user.id
    if caller_id == OWNER_ID:
        return True, None

    try:
        caller_member = await message.chat.get_member(caller_id)
        if caller_member.status not in [ChatMemberStatus.CREATOR, ChatMemberStatus.ADMINISTRATOR]:
            return False, "Missing Admin Permission"
    except Exception:
        return False, "Missing Admin Permission"

    return True, None


async def resolve_target(message: Message) -> Tuple[Optional[int], Optional[str], Optional[str]]:
    """
    Resolves moderation target across 3 methods:
    1. Reply to message: "/ban"
    2. Username: "/ban @username"
    3. User ID: "/ban 123456789"
    Returns: (target_id, target_tag, error_message)
    """
    # Method 1: Reply to a member's message
    if message.reply_to_message and message.reply_to_message.from_user:
        target = message.reply_to_message.from_user
        tag = format_user_tag(target.id, target.username, target.full_name)
        await register_user(target.id, target.username, target.full_name)
        return target.id, tag, None

    args = message.text.split()[1:] if message.text else []
    if not args:
        return None, None, "Target Not Found"

    raw_target = args[0].strip()

    # Method 3: Numeric User ID
    if raw_target.lstrip("-").isdigit():
        target_id = int(raw_target)
        if target_id <= 0:
            return None, None, "Invalid User ID"

        # Check in local database
        user_row = await get_user_by_id(target_id)
        if user_row:
            tag = format_user_tag(target_id, user_row.get("username"), user_row.get("full_name"))
            return target_id, tag, None

        # Try to query Telegram chat member
        try:
            member = await message.chat.get_member(target_id)
            if member and member.user:
                u = member.user
                await register_user(u.id, u.username, u.full_name)
                tag = format_user_tag(u.id, u.username, u.full_name)
                return target_id, tag, None
        except Exception:
            pass

        return None, None, "Member Not Found"

    # Method 2: Username (@username or plain username)
    clean_username = raw_target.lstrip("@").strip().lower()
    if clean_username:
        # Check local database
        user_row = await get_user_by_username(clean_username)
        if user_row:
            t_id = user_row["user_id"]
            tag = format_user_tag(t_id, user_row.get("username"), user_row.get("full_name"))
            return t_id, tag, None

        # Check administrators list in current chat
        try:
            admins = await message.chat.get_administrators()
            for adm in admins:
                if adm.user.username and adm.user.username.lower() == clean_username:
                    u = adm.user
                    await register_user(u.id, u.username, u.full_name)
                    tag = format_user_tag(u.id, u.username, u.full_name)
                    return u.id, tag, None
        except Exception:
            pass

        return None, None, "Member Not Found"

    return None, None, "Invalid User ID"


# ---------------- MODERATION COMMANDS ----------------

@router.message(Command("ban", ignore_case=True))
async def cmd_ban(message: Message):
    """
    /ban @username, /ban 123456789, or reply /ban
    Bans member permanently from group without confirmation.
    """
    is_ok, err_msg = await check_admin_rights(message)
    if not is_ok:
        await message.reply(err_msg or "Missing Admin Permission")
        return

    target_id, target_tag, err = await resolve_target(message)
    if err or not target_id:
        await message.reply(err or "Member Not Found")
        return

    if target_id == message.bot.id or target_id == message.from_user.id:
        await message.reply("Action Failed")
        return

    admin_tag = get_admin_tag(message.from_user)

    try:
        await message.chat.ban_member(user_id=target_id)
        await set_member_unmuted(message.chat.id, target_id)
        await log_moderation(
            group_id=message.chat.id,
            admin_id=message.from_user.id,
            admin_name=admin_tag,
            user_id=target_id,
            user_name=target_tag,
            action="BAN",
            reason="Banned by admin",
            duration="Permanen"
        )

        notification = (
            "𓄲 𓂃 𝐌𝐄𝐌𝐁𝐄𝐑 𝐁𝐀𝐍𝐍𝐄𝐃\n\n"
            f"Member: {target_tag}\n"
            "Status: Successfully Banned\n"
            f"Action By: {admin_tag}\n\n"
            "Member telah berhasil dikeluarkan secara permanen dari grup ASCHEN."
        )
        await message.reply(notification)
    except Exception as e:
        logger.error(f"Error banning member {target_id}: {e}")
        await message.reply("Action Failed")


@router.message(Command("unban", ignore_case=True))
async def cmd_unban(message: Message):
    """
    /unban @username, /unban 123456789, or reply /unban
    Unbans member without confirmation.
    """
    is_ok, err_msg = await check_admin_rights(message)
    if not is_ok:
        await message.reply(err_msg or "Missing Admin Permission")
        return

    target_id, target_tag, err = await resolve_target(message)
    if err or not target_id:
        await message.reply(err or "Member Not Found")
        return

    admin_tag = get_admin_tag(message.from_user)

    try:
        await message.chat.unban_member(user_id=target_id, only_if_banned=True)
        await log_moderation(
            group_id=message.chat.id,
            admin_id=message.from_user.id,
            admin_name=admin_tag,
            user_id=target_id,
            user_name=target_tag,
            action="UNBAN",
            reason="Unbanned by admin",
            duration="-"
        )

        notification = (
            "𓄲 𓂃 𝐌𝐄𝐌𝐁𝐄𝐑 𝐔𝐍𝐁𝐀𝐍𝐍𝐄𝐃\n\n"
            f"Member: {target_tag}\n"
            "Status: Successfully Unbanned\n"
            f"Action By: {admin_tag}\n\n"
            "Member telah berhasil dibuka blokirnya dan dapat bergabung kembali ke grup ASCHEN."
        )
        await message.reply(notification)
    except Exception as e:
        logger.error(f"Error unbanning member {target_id}: {e}")
        await message.reply("Action Failed")


@router.message(Command("mute", ignore_case=True))
async def cmd_mute(message: Message):
    """
    /mute @username, /mute 123456789, or reply /mute
    Mutes member indefinitely until unmuted. No duration asked.
    Sends notification with [ UNMUTE ] inline button.
    """
    is_ok, err_msg = await check_admin_rights(message)
    if not is_ok:
        await message.reply(err_msg or "Missing Admin Permission")
        return

    target_id, target_tag, err = await resolve_target(message)
    if err or not target_id:
        await message.reply(err or "Member Not Found")
        return

    if target_id == message.bot.id or target_id == message.from_user.id:
        await message.reply("Action Failed")
        return

    # Check if already muted in database or telegram status
    already_muted = await is_member_muted(message.chat.id, target_id)
    if not already_muted:
        try:
            cm = await message.chat.get_member(target_id)
            if cm.status == ChatMemberStatus.RESTRICTED and not getattr(cm, "can_send_messages", True):
                already_muted = True
        except Exception:
            pass

    if already_muted:
        await message.reply("Member Already Muted")
        return

    admin_tag = get_admin_tag(message.from_user)

    try:
        await message.chat.restrict_member(
            user_id=target_id,
            permissions=ChatPermissions(
                can_send_messages=False,
                can_send_photos=False,
                can_send_videos=False,
                can_send_other_messages=False,
                can_add_web_page_previews=False
            ),
            until_date=None
        )

        await set_member_muted(message.chat.id, target_id, message.from_user.id, admin_tag)
        await log_moderation(
            group_id=message.chat.id,
            admin_id=message.from_user.id,
            admin_name=admin_tag,
            user_id=target_id,
            user_name=target_tag,
            action="MUTE",
            reason="Muted by admin",
            duration="Indefinite"
        )

        # Inline button [ UNMUTE ]
        unmute_markup = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="[ UNMUTE ]", callback_data=f"mod_unmute:{target_id}")]
            ]
        )

        notification = (
            "𓄲 𓂃 𝐌𝐄𝐌𝐁𝐄𝐑 𝐌𝐔𝐓𝐄𝐃\n\n"
            f"Member: {target_tag}\n"
            "Status: Successfully Muted\n"
            f"Action By: {admin_tag}\n\n"
            "Member berhasil dibatasi dan tidak dapat mengirim pesan sementara."
        )
        await message.reply(notification, reply_markup=unmute_markup)
    except Exception as e:
        logger.error(f"Error muting member {target_id}: {e}")
        await message.reply("Action Failed")


@router.message(Command("unmute", ignore_case=True))
async def cmd_unmute(message: Message):
    """
    /unmute @username, /unmute 123456789, or reply /unmute
    Restores chat permissions without confirmation.
    """
    is_ok, err_msg = await check_admin_rights(message)
    if not is_ok:
        await message.reply(err_msg or "Missing Admin Permission")
        return

    target_id, target_tag, err = await resolve_target(message)
    if err or not target_id:
        await message.reply(err or "Member Not Found")
        return

    # Check if already unmuted
    is_muted = await is_member_muted(message.chat.id, target_id)
    if not is_muted:
        try:
            cm = await message.chat.get_member(target_id)
            if cm.status in [ChatMemberStatus.MEMBER, ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.CREATOR]:
                await message.reply("Member Already Unmuted")
                return
            if cm.status == ChatMemberStatus.RESTRICTED and getattr(cm, "can_send_messages", True):
                await message.reply("Member Already Unmuted")
                return
        except Exception:
            pass

    admin_tag = get_admin_tag(message.from_user)

    try:
        await message.chat.restrict_member(
            user_id=target_id,
            permissions=ChatPermissions(
                can_send_messages=True,
                can_send_photos=True,
                can_send_videos=True,
                can_send_other_messages=True,
                can_add_web_page_previews=True
            )
        )

        await set_member_unmuted(message.chat.id, target_id)
        await log_moderation(
            group_id=message.chat.id,
            admin_id=message.from_user.id,
            admin_name=admin_tag,
            user_id=target_id,
            user_name=target_tag,
            action="UNMUTE",
            reason="Unmuted by admin",
            duration="-"
        )

        notification = (
            "𓄲 𓂃 𝐌𝐄𝐌𝐁𝐄𝐑 𝐔𝐍𝐌𝐔𝐓𝐄𝐃\n\n"
            f"Member: {target_tag}\n"
            "Status: Successfully Unmuted\n"
            f"Action By: {admin_tag}\n\n"
            "Member telah berhasil mendapatkan kembali izin untuk mengirim pesan di grup ASCHEN."
        )
        await message.reply(notification)
    except Exception as e:
        logger.error(f"Error unmuting member {target_id}: {e}")
        await message.reply("Action Failed")


@router.message(Command("kick", ignore_case=True))
async def cmd_kick(message: Message):
    """
    /kick @username, /kick 123456789, or reply /kick
    Kicks member from group (can rejoin if not banned).
    """
    is_ok, err_msg = await check_admin_rights(message)
    if not is_ok:
        await message.reply(err_msg or "Missing Admin Permission")
        return

    target_id, target_tag, err = await resolve_target(message)
    if err or not target_id:
        await message.reply(err or "Member Not Found")
        return

    if target_id == message.bot.id or target_id == message.from_user.id:
        await message.reply("Action Failed")
        return

    admin_tag = get_admin_tag(message.from_user)

    try:
        # Telegram Kick: ban then immediately unban
        await message.chat.ban_member(user_id=target_id)
        await message.chat.unban_member(user_id=target_id)
        await set_member_unmuted(message.chat.id, target_id)

        await log_moderation(
            group_id=message.chat.id,
            admin_id=message.from_user.id,
            admin_name=admin_tag,
            user_id=target_id,
            user_name=target_tag,
            action="KICK",
            reason="Kicked by admin",
            duration="-"
        )

        notification = (
            "𓄲 𓂃 𝐌𝐄𝐌𝐁𝐄𝐑 𝐊𝐈𝐂𝐊𝐄𝐃\n\n"
            f"Member: {target_tag}\n"
            "Status: Successfully Kicked\n"
            f"Action By: {admin_tag}\n\n"
            "Member berhasil dikeluarkan dari grup ASCHEN."
        )
        await message.reply(notification)
    except Exception as e:
        logger.error(f"Error kicking member {target_id}: {e}")
        await message.reply("Action Failed")


# ---------------- CALLBACK: INLINE [ UNMUTE ] BUTTON ----------------

@router.callback_query(F.data.startswith("mod_unmute:"))
async def cb_mod_unmute(callback: CallbackQuery):
    """
    Handles the [ UNMUTE ] inline button on muted notifications.
    Ensures only authorized admins can unmute.
    Removes button and updates message to MEMBER UNMUTED.
    """
    chat = callback.message.chat
    admin_id = callback.from_user.id

    # Verify caller admin rights
    if admin_id != OWNER_ID:
        try:
            admin_member = await chat.get_member(admin_id)
            if admin_member.status not in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.CREATOR]:
                await callback.answer("Missing Admin Permission", show_alert=True)
                return
        except Exception:
            await callback.answer("Missing Admin Permission", show_alert=True)
            return

    target_id_str = callback.data.split(":")[1]
    if not target_id_str.isdigit():
        await callback.answer("Invalid User ID", show_alert=True)
        return

    target_id = int(target_id_str)

    # Check if target is currently muted
    is_muted = await is_member_muted(chat.id, target_id)
    if not is_muted:
        try:
            cm = await chat.get_member(target_id)
            if cm.status in [ChatMemberStatus.MEMBER, ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.CREATOR]:
                await callback.answer("Status mute sudah tidak aktif.", show_alert=True)
                try:
                    await callback.message.edit_reply_markup(reply_markup=None)
                except Exception:
                    pass
                return
            if cm.status == ChatMemberStatus.RESTRICTED and getattr(cm, "can_send_messages", True):
                await callback.answer("Status mute sudah tidak aktif.", show_alert=True)
                try:
                    await callback.message.edit_reply_markup(reply_markup=None)
                except Exception:
                    pass
                return
        except Exception:
            pass

    # Perform Unmute in Telegram
    try:
        await chat.restrict_member(
            user_id=target_id,
            permissions=ChatPermissions(
                can_send_messages=True,
                can_send_photos=True,
                can_send_videos=True,
                can_send_other_messages=True,
                can_add_web_page_previews=True
            )
        )
    except Exception as e:
        logger.error(f"Error unmuting via button {target_id}: {e}")
        await callback.answer("Action Failed", show_alert=True)
        return

    await set_member_unmuted(chat.id, target_id)

    # Determine target tag
    user_row = await get_user_by_id(target_id)
    if user_row:
        target_tag = format_user_tag(target_id, user_row.get("username"), user_row.get("full_name"))
    else:
        try:
            cm = await chat.get_member(target_id)
            target_tag = format_user_tag(target_id, cm.user.username, cm.user.full_name)
        except Exception:
            target_tag = f"User {target_id}"

    admin_tag = get_admin_tag(callback.from_user)

    await log_moderation(
        group_id=chat.id,
        admin_id=callback.from_user.id,
        admin_name=admin_tag,
        user_id=target_id,
        user_name=target_tag,
        action="UNMUTE",
        reason="Unmuted via inline button",
        duration="-"
    )

    # Edit notification message and remove button
    updated_text = (
        "𓄲 𓂃 𝐌𝐄𝐌𝐁𝐄𝐑 𝐔𝐍𝐌𝐔𝐓𝐄𝐃\n\n"
        f"Member: {target_tag}\n"
        "Status: Successfully Unmuted\n"
        f"Action By: {admin_tag}\n\n"
        "Member telah berhasil mendapatkan kembali izin untuk mengirim pesan di grup ASCHEN."
    )

    try:
        await callback.message.edit_text(updated_text, reply_markup=None)
    except Exception:
        try:
            await callback.message.edit_reply_markup(reply_markup=None)
        except Exception:
            pass

    await callback.answer("Member successfully unmuted!")


# ---------------- AUTOMATIC GROUP WELCOME SYSTEM ----------------

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
