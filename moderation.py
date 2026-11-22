"""
ASCHI BOT — GROUP MODERATION SYSTEM & PERMISSION CHECKER
ASCHEN EVENT ORGANIZER
Handles Mandatory Group Administrator verification, automatic permission checks,
and the 5 core moderation commands: /BAN, /MUTE, /KICK, /UNBAN, /UNMUTE.
"""

import re
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple
from aiogram import Router, F
from aiogram.types import (
    Message,
    ChatMemberUpdated,
    ChatPermissions,
)
from aiogram.filters import Command, ChatMemberUpdatedFilter, JOIN_TRANSITION, PROMOTED_TRANSITION
from aiogram.enums import ChatMemberStatus, ChatType
from database import update_group_status, log_moderation, get_setting
from config import TITLE_DECOR, FOOTER_DECOR

router = Router(name="moderation")

# Exact notices as specified in requirements
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


# ---------------- AUTOMATIC PERMISSION CHECKER ----------------

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


# ---------------- HELPER VALIDATIONS ----------------

async def check_admin_rights(message: Message) -> Tuple[bool, Optional[str]]:
    """
    Checks whether:
    1. Message is in a group or supergroup
    2. Bot is an administrator with restrict members permission
    3. The command issuer is a group administrator/creator
    """
    if message.chat.type not in [ChatType.GROUP, ChatType.SUPERGROUP]:
        return False, "Perintah moderasi hanya dapat digunakan di dalam Grup Telegram."

    # Check bot admin status
    bot_member = await message.chat.get_member(message.bot.id)
    if bot_member.status != ChatMemberStatus.ADMINISTRATOR or not getattr(bot_member, "can_restrict_members", False):
        await message.reply(NOTICE_NOT_ADMIN)
        return False, None

    # Check caller admin status
    user_member = await message.chat.get_member(message.from_user.id)
    if user_member.status not in [ChatMemberStatus.CREATOR, ChatMemberStatus.ADMINISTRATOR]:
        return False, "Anda harus menjadi Administrator grup untuk menjalankan perintah ini."

    return True, None


def parse_target_and_reason(message: Message) -> Tuple[Optional[int], Optional[str], str]:
    """
    Extracts target user ID, target name, and reason from reply or arguments.
    Supports:
    - Reply to message: /ban [reason]
    - Direct user id: /ban 12345678 [reason]
    """
    args = message.text.split()[1:] if message.text else []

    if message.reply_to_message:
        target_id = message.reply_to_message.from_user.id
        target_name = message.reply_to_message.from_user.full_name
        reason = " ".join(args) if args else "Melanggar tata tertib grup"
        return target_id, target_name, reason

    if args and args[0].lstrip("-").isdigit():
        target_id = int(args[0])
        target_name = f"User {target_id}"
        reason = " ".join(args[1:]) if len(args) > 1 else "Melanggar tata tertib grup"
        return target_id, target_name, reason

    return None, None, ""


def parse_duration(arg_str: str) -> Tuple[Optional[timedelta], str]:
    """
    Parses duration strings like 10m, 1h, 1d, 7d.
    Returns (timedelta, remaining_text).
    """
    match = re.match(r"^(\d+)([mhd])$", arg_str.lower())
    if match:
        amount, unit = int(match.group(1)), match.group(2)
        if unit == "m":
            return timedelta(minutes=amount), f"{amount} Menit"
        elif unit == "h":
            return timedelta(hours=amount), f"{amount} Jam"
        elif unit == "d":
            return timedelta(days=amount), f"{amount} Hari"
    return None, ""


# ---------------- MODERATION COMMANDS ----------------

@router.message(Command("ban", ignore_case=True))
async def cmd_ban(message: Message):
    """Ban member from group."""
    if await get_setting("mod_ban_enabled", "1") != "1":
        await message.reply("Fitur /BAN sedang dinonaktifkan oleh administrator.")
        return

    is_ok, err_msg = await check_admin_rights(message)
    if not is_ok:
        if err_msg:
            await message.reply(err_msg)
        return

    target_id, target_name, reason = parse_target_and_reason(message)
    if not target_id:
        await message.reply(
            "Gunakan perintah ini dengan membalas (reply) pesan anggota atau sebutkan User ID:\n"
            "Contoh: <code>/ban [alasan]</code> (reply pesan) atau <code>/ban 12345678 [alasan]</code>",
            parse_mode="HTML"
        )
        return

    if target_id == message.bot.id or target_id == message.from_user.id:
        await message.reply("Perintah tidak valid untuk akun ini.")
        return

    try:
        await message.chat.ban_member(user_id=target_id)
        await log_moderation(
            group_id=message.chat.id,
            admin_id=message.from_user.id,
            admin_name=message.from_user.full_name,
            user_id=target_id,
            user_name=target_name,
            action="BAN",
            reason=reason,
            duration="Permanen"
        )

        resp = (
            f"{TITLE_DECOR}\n\n"
            f"🛡️ <b>MEMBER BANNED</b>\n\n"
            f"• <b>Anggota:</b> {target_name} (<code>{target_id}</code>)\n"
            f"• <b>Admin:</b> {message.from_user.full_name}\n"
            f"• <b>Alasan:</b> {reason}\n"
            f"• <b>Tindakan:</b> Diblokir dari grup\n\n"
            f"{FOOTER_DECOR}"
        )
        await message.reply(resp, parse_mode="HTML")
    except Exception as e:
        await message.reply(f"Gagal melakukan ban: {e}")


@router.message(Command("mute", ignore_case=True))
async def cmd_mute(message: Message):
    """Mute member with optional duration (e.g. /mute 10m, /mute 1h, /mute 1d)."""
    if await get_setting("mod_mute_enabled", "1") != "1":
        await message.reply("Fitur /MUTE sedang dinonaktifkan oleh administrator.")
        return

    is_ok, err_msg = await check_admin_rights(message)
    if not is_ok:
        if err_msg:
            await message.reply(err_msg)
        return

    args = message.text.split()[1:] if message.text else []
    target_id = None
    target_name = None
    duration_delta = timedelta(hours=1)
    duration_text = "1 Jam (Default)"
    reason_parts = []

    if message.reply_to_message:
        target_id = message.reply_to_message.from_user.id
        target_name = message.reply_to_message.from_user.full_name
        if args:
            d_delta, d_label = parse_duration(args[0])
            if d_delta:
                duration_delta = d_delta
                duration_text = d_label
                reason_parts = args[1:]
            else:
                reason_parts = args
    elif args and args[0].lstrip("-").isdigit():
        target_id = int(args[0])
        target_name = f"User {target_id}"
        if len(args) > 1:
            d_delta, d_label = parse_duration(args[1])
            if d_delta:
                duration_delta = d_delta
                duration_text = d_label
                reason_parts = args[2:]
            else:
                reason_parts = args[1:]
    else:
        await message.reply(
            "Gunakan perintah ini dengan membalas (reply) pesan anggota atau sebutkan User ID:\n"
            "Contoh:\n"
            "• <code>/mute 10m [alasan]</code> (reply pesan)\n"
            "• <code>/mute 1h Spamming</code>\n"
            "• <code>/mute 12345678 1d Melanggar aturan</code>",
            parse_mode="HTML"
        )
        return

    if target_id == message.bot.id or target_id == message.from_user.id:
        await message.reply("Perintah tidak valid untuk akun ini.")
        return

    reason = " ".join(reason_parts) if reason_parts else "Membatasi aktivitas pesan"
    until_date = datetime.now(timezone.utc) + duration_delta

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
            until_date=until_date
        )

        await log_moderation(
            group_id=message.chat.id,
            admin_id=message.from_user.id,
            admin_name=message.from_user.full_name,
            user_id=target_id,
            user_name=target_name,
            action="MUTE",
            reason=reason,
            duration=duration_text
        )

        resp = (
            f"{TITLE_DECOR}\n\n"
            f"🔇 <b>MEMBER MUTED</b>\n\n"
            f"• <b>Anggota:</b> {target_name} (<code>{target_id}</code>)\n"
            f"• <b>Admin:</b> {message.from_user.full_name}\n"
            f"• <b>Durasi:</b> {duration_text}\n"
            f"• <b>Alasan:</b> {reason}\n"
            f"• <b>Tindakan:</b> Pembatasan izin kirim pesan aktif\n\n"
            f"{FOOTER_DECOR}"
        )
        await message.reply(resp, parse_mode="HTML")
    except Exception as e:
        await message.reply(f"Gagal melakukan mute: {e}")


@router.message(Command("kick", ignore_case=True))
async def cmd_kick(message: Message):
    """Kick member from group (can rejoin if not banned)."""
    if await get_setting("mod_kick_enabled", "1") != "1":
        await message.reply("Fitur /KICK sedang dinonaktifkan oleh administrator.")
        return

    is_ok, err_msg = await check_admin_rights(message)
    if not is_ok:
        if err_msg:
            await message.reply(err_msg)
        return

    target_id, target_name, reason = parse_target_and_reason(message)
    if not target_id:
        await message.reply(
            "Gunakan perintah ini dengan membalas pesan anggota atau sebutkan User ID:\n"
            "Contoh: <code>/kick [alasan]</code> atau <code>/kick 12345678 [alasan]</code>",
            parse_mode="HTML"
        )
        return

    if target_id == message.bot.id or target_id == message.from_user.id:
        await message.reply("Perintah tidak valid untuk akun ini.")
        return

    try:
        # Kick in Telegram: ban then immediately unban
        await message.chat.ban_member(user_id=target_id)
        await message.chat.unban_member(user_id=target_id)

        await log_moderation(
            group_id=message.chat.id,
            admin_id=message.from_user.id,
            admin_name=message.from_user.full_name,
            user_id=target_id,
            user_name=target_name,
            action="KICK",
            reason=reason,
            duration="-"
        )

        resp = (
            f"{TITLE_DECOR}\n\n"
            f"👢 <b>MEMBER KICKED</b>\n\n"
            f"• <b>Anggota:</b> {target_name} (<code>{target_id}</code>)\n"
            f"• <b>Admin:</b> {message.from_user.full_name}\n"
            f"• <b>Alasan:</b> {reason}\n"
            f"• <b>Keterangan:</b> Anggota dapat bergabung kembali melalui undangan\n\n"
            f"{FOOTER_DECOR}"
        )
        await message.reply(resp, parse_mode="HTML")
    except Exception as e:
        await message.reply(f"Gagal mengeluarkan anggota: {e}")


@router.message(Command("unban", ignore_case=True))
async def cmd_unban(message: Message):
    """Unban member."""
    if await get_setting("mod_unban_enabled", "1") != "1":
        await message.reply("Fitur /UNBAN sedang dinonaktifkan oleh administrator.")
        return

    is_ok, err_msg = await check_admin_rights(message)
    if not is_ok:
        if err_msg:
            await message.reply(err_msg)
        return

    target_id, target_name, _ = parse_target_and_reason(message)
    if not target_id:
        await message.reply(
            "Gunakan perintah ini dengan reply pesan atau User ID:\n"
            "Contoh: <code>/unban 12345678</code>",
            parse_mode="HTML"
        )
        return

    try:
        await message.chat.unban_member(user_id=target_id)
        await log_moderation(
            group_id=message.chat.id,
            admin_id=message.from_user.id,
            admin_name=message.from_user.full_name,
            user_id=target_id,
            user_name=target_name,
            action="UNBAN",
            reason="Pencabutan blokir oleh admin",
            duration="-"
        )

        resp = (
            f"{TITLE_DECOR}\n\n"
            f"🔓 <b>MEMBER UNBANNED</b>\n\n"
            f"• <b>Anggota:</b> {target_name} (<code>{target_id}</code>)\n"
            f"• <b>Admin:</b> {message.from_user.full_name}\n"
            f"• <b>Status:</b> Blokir telah dicabut\n\n"
            f"{FOOTER_DECOR}"
        )
        await message.reply(resp, parse_mode="HTML")
    except Exception as e:
        await message.reply(f"Gagal membuka blokir: {e}")


@router.message(Command("unmute", ignore_case=True))
async def cmd_unmute(message: Message):
    """Unmute member, restoring chat permissions."""
    if await get_setting("mod_unmute_enabled", "1") != "1":
        await message.reply("Fitur /UNMUTE sedang dinonaktifkan oleh administrator.")
        return

    is_ok, err_msg = await check_admin_rights(message)
    if not is_ok:
        if err_msg:
            await message.reply(err_msg)
        return

    target_id, target_name, _ = parse_target_and_reason(message)
    if not target_id:
        await message.reply(
            "Gunakan perintah ini dengan reply pesan atau User ID:\n"
            "Contoh: <code>/unmute 12345678</code>",
            parse_mode="HTML"
        )
        return

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

        await log_moderation(
            group_id=message.chat.id,
            admin_id=message.from_user.id,
            admin_name=message.from_user.full_name,
            user_id=target_id,
            user_name=target_name,
            action="UNMUTE",
            reason="Pemulihan izin kirim pesan oleh admin",
            duration="-"
        )

        resp = (
            f"{TITLE_DECOR}\n\n"
            f"🔊 <b>MEMBER UNMUTED</b>\n\n"
            f"• <b>Anggota:</b> {target_name} (<code>{target_id}</code>)\n"
            f"• <b>Admin:</b> {message.from_user.full_name}\n"
            f"• <b>Status:</b> Izin mengirim pesan telah dipulihkan\n\n"
            f"{FOOTER_DECOR}"
        )
        await message.reply(resp, parse_mode="HTML")
    except Exception as e:
        await message.reply(f"Gagal memulihkan izin pesan: {e}")
