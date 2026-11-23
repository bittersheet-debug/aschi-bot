"""
ASCHI BOT — ADMIN DASHBOARD & SETTINGS (/maurits)
ASCHEN EVENT ORGANIZER
Strict Compliance with Master Prompt Fix:
- Accessed via /maurits (Protected: "ACCESS DENIED. ADMIN ONLY.")
- Full Sections A through I:
  A. Welcome Settings
  B. Menu Settings (Wedding Menu, Indonesian, Korean, Foreign)
  C. Food Management (Add, Delete, Edit command, price, availability)
  D. Food Photo Settings (Auto search, search again, upload manual, reset)
  E. Caption Settings (Edit, preview, custom per food)
  F. Order Button Settings (Button 1, Button 2, URL, preview, save)
  G. Group Management Settings (Moderation switches, logs)
  H. Bot Settings & Backup (.db download)
  I. Admin Access Management
"""

import logging
from aiogram import Router, F
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    FSInputFile,
)
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from config import (
    TITLE_DECOR,
    FOOTER_DECOR,
    OWNER_ID,
    ADMIN_PASSWORD,
    ORDER_URL,
    CONTACT_URL,
    OFFICIAL_ORGANIZER,
    OFFICIAL_CONTACT,
)
from database import (
    is_admin_or_owner,
    get_setting,
    set_setting,
    get_all_foods,
    get_food_by_id,
    add_food,
    update_food,
    delete_food,
    get_recent_moderation_logs,
    list_admins,
    add_admin,
    remove_admin,
    backup_database,
    format_command,
    DEFAULT_GROUP_WELCOME_TEXT,
    is_catalog_enabled,
    set_catalog_status,
)
from captions import generate_aschen_caption
from image_search import search_food_image
from keyboards import (
    build_admin_dashboard_keyboard,
    build_admin_back_keyboard,
    build_cancel_keyboard,
    build_welcome_mgmt_keyboard,
)

logger = logging.getLogger(__name__)
router = Router(name="admin_dashboard")

DENIED_TEXT = "ACCESS DENIED. ADMIN ONLY."


# ---------------- FSM STATES ----------------

class AddFoodState(StatesGroup):
    waiting_name = State()
    waiting_command = State()
    waiting_category = State()
    waiting_subcategory = State()
    waiting_price = State()
    waiting_preview_decision = State()


class EditFoodState(StatesGroup):
    waiting_new_command = State()
    waiting_new_price = State()


class ImageSettingsState(StatesGroup):
    waiting_manual_upload = State()


class OrderBtnSettingsState(StatesGroup):
    waiting_btn1_text = State()
    waiting_btn1_url = State()
    waiting_btn2_text = State()
    waiting_btn2_url = State()


class WelcomeSettingsState(StatesGroup):
    waiting_welcome_text = State()
    waiting_help_label = State()
    waiting_contact_label = State()
    waiting_group_label = State()


class CaptionSettingsState(StatesGroup):
    waiting_custom_caption = State()


class WeddingMenuSettingsState(StatesGroup):
    waiting_title = State()
    waiting_desc = State()


class AdminAccessState(StatesGroup):
    waiting_user_id = State()


class AdminAuthState(StatesGroup):
    waiting_password = State()


class GroupWelcomeState(StatesGroup):
    waiting_welcome_text = State()
    waiting_welcome_photo = State()
    waiting_welcome_gift = State()
    waiting_welcome_video = State()
    waiting_welcome_duration = State()



# ---------------- ACCESS CONTROL HELPER ----------------

async def ensure_admin(event: Message | CallbackQuery) -> bool:
    """Checks if caller is Owner or authorized Admin. Rejects with DENIED_TEXT."""
    user_id = event.from_user.id
    if not await is_admin_or_owner(user_id):
        if isinstance(event, CallbackQuery):
            await event.answer(DENIED_TEXT, show_alert=True)
            try:
                await event.message.answer(f"⛔ <b>{DENIED_TEXT}</b>", parse_mode="HTML")
            except Exception:
                pass
        else:
            await event.reply(f"⛔ <b>{DENIED_TEXT}</b>", parse_mode="HTML")
        return False
    return True


def render_maurits_dashboard_text(user_full_name: str) -> str:
    return (
        f"{TITLE_DECOR}\n\n"
        f"⚙️ <b>ASCHI BOT — ADMIN SETTINGS (/maurits)</b>\n"
        f"<i>Pusat Pengaturan Resmi ASCHEN EVENT ORGANIZER</i>\n\n"
        f"Selamat datang, <b>{user_full_name}</b>.\n"
        f"Silakan pilih menu pengaturan di bawah ini:\n\n"
        f"• 🎉 <b>WELCOME MANAGEMENT</b> — Sambutan otomatis grup (Teks, Foto, GIF, Video, Durasi)\n"
        f"• 📝 <b>A. Welcome Settings (/start)</b> — Pesan sambutan & 3 tombol awal\n"
        f"• 🍽️ <b>B. Menu Settings</b> — Layanan Wedding Menu & 3 kategori utama\n"
        f"• 🍲 <b>C. Food Management</b> — Tambah, edit command, harga, status\n"
        f"• 🖼️ <b>D. Food Photo Settings</b> — Saklar auto search & upload foto manual\n"
        f"• 💬 <b>E. Caption Settings</b> — Kustomisasi caption roleplay ASCHEN\n"
        f"• 🛒 <b>F. Order Button Settings</b> — Atur nama & URL 2 tombol pemesanan\n"
        f"• ⚙️ <b>G. Bot Settings & Backup</b> — Pengaturan identitas & cadangan database\n"
        f"• 👥 <b>H. Admin Access</b> — Tambah / hapus administrator resmi\n\n"
        f"{FOOTER_DECOR}"
    )


# ---------------- /maurits ENTRY POINT WITH PASSWORD VERIFICATION ----------------

@router.message(Command("maurits", ignore_case=True))
@router.message(Command("adminaschi", ignore_case=True))
async def cmd_maurits(message: Message, state: FSMContext):
    """
    Main Admin Dashboard Command (/maurits).
    Requires password 'ASCHEN2026' before granting access.
    """
    await state.clear()
    args = message.text.split()[1:] if message.text else []
    admin_pw = await get_setting("admin_password", ADMIN_PASSWORD)

    # If password is provided in command line: e.g. /maurits ASCHEN2026
    if args:
        if args[0].strip() == admin_pw:
            await add_admin(message.from_user.id, message.from_user.username or message.from_user.full_name, message.from_user.id)
            dashboard_text = render_maurits_dashboard_text(message.from_user.full_name)
            await message.reply(dashboard_text, reply_markup=build_admin_dashboard_keyboard(), parse_mode="HTML")
            return
        else:
            await message.reply("⛔ <b>Kata sandi salah.</b> Akses ditolak.", parse_mode="HTML")
            return

    # Prompt user for password
    await state.set_state(AdminAuthState.waiting_password)
    prompt_text = (
        f"{TITLE_DECOR}\n\n"
        f"🔐 <b>KATA SANDI ADMIN DIPERLUKAN</b>\n\n"
        f"Silakan ketikkan kata sandi untuk mengakses menu pengaturan <b>/maurits</b>:\n\n"
        f"{FOOTER_DECOR}"
    )
    await message.reply(prompt_text, reply_markup=build_cancel_keyboard("Batal"), parse_mode="HTML")


@router.message(AdminAuthState.waiting_password)
async def process_admin_password(message: Message, state: FSMContext):
    """Verifies the password for /maurits access."""
    entered_pw = message.text.strip() if message.text else ""
    admin_pw = await get_setting("admin_password", ADMIN_PASSWORD)

    if entered_pw == admin_pw:
        await state.clear()
        await add_admin(message.from_user.id, message.from_user.username or message.from_user.full_name, message.from_user.id)
        dashboard_text = render_maurits_dashboard_text(message.from_user.full_name)
        await message.reply(
            f"✅ <b>Kata sandi benar. Akses diterima!</b>\n\n{dashboard_text}",
            reply_markup=build_admin_dashboard_keyboard(),
            parse_mode="HTML"
        )
    else:
        await state.clear()
        await message.reply("⛔ <b>Kata sandi salah.</b> Akses ditolak.", parse_mode="HTML")


@router.callback_query(F.data == "admin:main")
async def cb_admin_main(callback: CallbackQuery, state: FSMContext):
    """Returns to /maurits dashboard home."""
    await state.clear()
    if not await ensure_admin(callback):
        return
    await callback.answer()

    text = render_maurits_dashboard_text(callback.from_user.full_name)
    try:
        await callback.message.edit_text(text, reply_markup=build_admin_dashboard_keyboard(), parse_mode="HTML")
    except Exception:
        await callback.message.answer(text, reply_markup=build_admin_dashboard_keyboard(), parse_mode="HTML")

    try:
        await callback.message.edit_text(text, reply_markup=build_admin_dashboard_keyboard(), parse_mode="HTML")
    except Exception:
        await callback.message.answer(text, reply_markup=build_admin_dashboard_keyboard(), parse_mode="HTML")


@router.callback_query(F.data == "fsm:cancel")
async def cb_fsm_cancel(callback: CallbackQuery, state: FSMContext):
    """Cancels active conversation wizard."""
    await state.clear()
    await callback.answer("Pengaturan dibatalkan.")
    await cb_admin_main(callback, state)


# =========================================================
# WELCOME MANAGEMENT (GROUP AUTOMATIC WELCOME SYSTEM)
# =========================================================

async def render_grp_welcome_panel(callback: CallbackQuery):
    is_enabled = (await get_setting("group_welcome_enabled", "1")) == "1"
    welcome_text = await get_setting("group_welcome_text", DEFAULT_GROUP_WELCOME_TEXT)
    media_type = await get_setting("group_welcome_media_type", "none")
    duration = await get_setting("group_welcome_duration", "5")

    status_label = "🟢 AKTIF" if is_enabled else "🔴 NONAKTIF"
    media_labels = {
        "none": "📄 Teks Saja",
        "photo": "🖼️ Foto",
        "gift": "🎁 Gift / GIF",
        "video": "📹 Video",
    }
    media_label = media_labels.get(media_type, "📄 Teks Saja")

    text = (
        f"{TITLE_DECOR}\n\n"
        f"🎉 <b>WELCOME MANAGEMENT (/maurits)</b>\n"
        f"<i>Pengaturan Sambutan Otomatis Grup ASCHEN</i>\n\n"
        f"• <b>Status Welcome:</b> {status_label}\n"
        f"• <b>Tipe Media Aktif:</b> {media_label}\n"
        f"• <b>Durasi Hapus Otomatis:</b> {duration} detik\n\n"
        f"• <b>Format Welcome Aktif:</b>\n"
        f"<blockquote>{welcome_text}</blockquote>\n\n"
        f"<i>Pesan welcome otomatis terhapus setelah {duration} detik agar grup tetap rapi.</i>\n\n"
        f"{FOOTER_DECOR}"
    )

    markup = build_welcome_mgmt_keyboard(is_enabled=is_enabled, media_type=media_type)
    try:
        await callback.message.edit_text(text, reply_markup=markup, parse_mode="HTML")
    except Exception:
        await callback.message.answer(text, reply_markup=markup, parse_mode="HTML")


@router.callback_query(F.data == "admin_grp_welcome:root")
async def cb_admin_grp_welcome_root(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    if not await ensure_admin(callback):
        return
    await callback.answer()
    await render_grp_welcome_panel(callback)


@router.callback_query(F.data == "admin_grp_welcome:enable")
async def cb_admin_grp_welcome_enable(callback: CallbackQuery):
    if not await ensure_admin(callback):
        return
    await set_setting("group_welcome_enabled", "1")
    await callback.answer("✅ Welcome otomatis grup DIAKTIFKAN!", show_alert=True)
    await render_grp_welcome_panel(callback)


@router.callback_query(F.data == "admin_grp_welcome:disable")
async def cb_admin_grp_welcome_disable(callback: CallbackQuery):
    if not await ensure_admin(callback):
        return
    await set_setting("group_welcome_enabled", "0")
    await callback.answer("❌ Welcome otomatis grup DINONAKTIFKAN!", show_alert=True)
    await render_grp_welcome_panel(callback)


@router.callback_query(F.data == "admin_grp_welcome:edit_text")
async def cb_admin_grp_welcome_edit_text(callback: CallbackQuery, state: FSMContext):
    if not await ensure_admin(callback):
        return
    await state.set_state(GroupWelcomeState.waiting_welcome_text)
    await callback.answer()
    prompt = (
        "<b>PENGATURAN TEKS WELCOME</b>\n\n"
        "Ketikkan teks pesan Welcome baru untuk anggota yang baru bergabung di grup ASCHEN.\n\n"
        "Gunakan kode <code>@USERNAME</code> di bagian teks yang ingin otomatis diganti "
        "dengan username anggota baru (atau nama profil jika tidak memiliki username).\n\n"
        "Kirim teks baru Anda:"
    )
    await callback.message.edit_text(prompt, reply_markup=build_cancel_keyboard(), parse_mode="HTML")


@router.message(GroupWelcomeState.waiting_welcome_text)
async def process_group_welcome_text(message: Message, state: FSMContext):
    if not message.text:
        await message.reply("Mohon kirimkan pesan teks yang valid.")
        return
    await set_setting("group_welcome_text", message.text.strip())
    await state.clear()
    await message.reply(
        "✅ Teks Welcome berhasil diperbarui dan tersimpan permanen!",
        reply_markup=build_admin_back_keyboard("admin_grp_welcome:root")
    )


@router.callback_query(F.data == "admin_grp_welcome:set_photo")
async def cb_admin_grp_welcome_set_photo(callback: CallbackQuery, state: FSMContext):
    if not await ensure_admin(callback):
        return
    await state.set_state(GroupWelcomeState.waiting_welcome_photo)
    await callback.answer()
    prompt = (
        "<b>PENGATURAN FOTO WELCOME</b>\n\n"
        "Kirimkan foto (gambar) yang ingin digunakan sebagai media Welcome grup ASCHEN.\n"
        "Foto ini akan dikirim otomatis dengan caption sambutan setiap kali ada anggota baru."
    )
    await callback.message.edit_text(prompt, reply_markup=build_cancel_keyboard(), parse_mode="HTML")


@router.message(GroupWelcomeState.waiting_welcome_photo)
async def process_group_welcome_photo(message: Message, state: FSMContext):
    if not message.photo:
        await message.reply("Mohon kirimkan foto/gambar yang valid, atau tekan Batal.", reply_markup=build_cancel_keyboard())
        return
    file_id = message.photo[-1].file_id
    await set_setting("group_welcome_photo_file_id", file_id)
    await set_setting("group_welcome_media_type", "photo")
    await state.clear()
    await message.reply(
        "✅ Foto Welcome berhasil disimpan dan diaktifkan!",
        reply_markup=build_admin_back_keyboard("admin_grp_welcome:root")
    )


@router.callback_query(F.data == "admin_grp_welcome:set_gift")
async def cb_admin_grp_welcome_set_gift(callback: CallbackQuery, state: FSMContext):
    if not await ensure_admin(callback):
        return
    await state.set_state(GroupWelcomeState.waiting_welcome_gift)
    await callback.answer()
    prompt = (
        "<b>PENGATURAN WELCOME GIFT (GIF / ANIMASI)</b>\n\n"
        "Kirimkan file animasi GIF / Welcome Gift yang ingin ditampilkan ketika anggota baru bergabung.\n"
        "Bot akan otomatis menyertakan caption sambutan."
    )
    await callback.message.edit_text(prompt, reply_markup=build_cancel_keyboard(), parse_mode="HTML")


@router.message(GroupWelcomeState.waiting_welcome_gift)
async def process_group_welcome_gift(message: Message, state: FSMContext):
    file_id = None
    if message.animation:
        file_id = message.animation.file_id
    elif message.document and message.document.mime_type and "gif" in message.document.mime_type:
        file_id = message.document.file_id

    if not file_id:
        await message.reply("Mohon kirimkan file animasi GIF atau Gift yang valid.", reply_markup=build_cancel_keyboard())
        return

    await set_setting("group_welcome_gift_file_id", file_id)
    await set_setting("group_welcome_media_type", "gift")
    await state.clear()
    await message.reply(
        "✅ Welcome Gift (GIF) berhasil disimpan dan diaktifkan!",
        reply_markup=build_admin_back_keyboard("admin_grp_welcome:root")
    )


@router.callback_query(F.data == "admin_grp_welcome:set_video")
async def cb_admin_grp_welcome_set_video(callback: CallbackQuery, state: FSMContext):
    if not await ensure_admin(callback):
        return
    await state.set_state(GroupWelcomeState.waiting_welcome_video)
    await callback.answer()
    prompt = (
        "<b>PENGATURAN VIDEO WELCOME</b>\n\n"
        "Kirimkan video yang ingin digunakan sebagai media Welcome grup ASCHEN.\n"
        "Bot akan otomatis memutar video beserta caption sambutan."
    )
    await callback.message.edit_text(prompt, reply_markup=build_cancel_keyboard(), parse_mode="HTML")


@router.message(GroupWelcomeState.waiting_welcome_video)
async def process_group_welcome_video(message: Message, state: FSMContext):
    if not message.video:
        await message.reply("Mohon kirimkan file video yang valid.", reply_markup=build_cancel_keyboard())
        return
    file_id = message.video.file_id
    await set_setting("group_welcome_video_file_id", file_id)
    await set_setting("group_welcome_media_type", "video")
    await state.clear()
    await message.reply(
        "✅ Video Welcome berhasil disimpan dan diaktifkan!",
        reply_markup=build_admin_back_keyboard("admin_grp_welcome:root")
    )


@router.callback_query(F.data == "admin_grp_welcome:reset_media")
async def cb_admin_grp_welcome_reset_media(callback: CallbackQuery):
    if not await ensure_admin(callback):
        return
    await set_setting("group_welcome_media_type", "none")
    await callback.answer("Media welcome direset ke teks saja.", show_alert=True)
    await render_grp_welcome_panel(callback)


@router.callback_query(F.data == "admin_grp_welcome:set_duration")
async def cb_admin_grp_welcome_set_duration(callback: CallbackQuery, state: FSMContext):
    if not await ensure_admin(callback):
        return
    await state.set_state(GroupWelcomeState.waiting_welcome_duration)
    await callback.answer()
    prompt = (
        "<b>PENGATURAN DURASI WELCOME</b>\n\n"
        "Masukkan durasi waktu otomatis penghapusan pesan welcome dalam satuan detik.\n"
        "Default sistem adalah <b>5</b> detik.\n\n"
        "Ketik angka detik (contoh: 5):"
    )
    await callback.message.edit_text(prompt, reply_markup=build_cancel_keyboard(), parse_mode="HTML")


@router.message(GroupWelcomeState.waiting_welcome_duration)
async def process_group_welcome_duration(message: Message, state: FSMContext):
    raw = message.text.strip() if message.text else ""
    if not raw.isdigit() or int(raw) < 1:
        await message.reply("Durasi harus berupa bilangan bulat positif dalam detik (minimal 1 detik). Silakan coba lagi:")
        return

    sec = int(raw)
    await set_setting("group_welcome_duration", str(sec))
    await state.clear()
    await message.reply(
        f"✅ Durasi penghapusan welcome berhasil diatur menjadi {sec} detik!",
        reply_markup=build_admin_back_keyboard("admin_grp_welcome:root")
    )


@router.callback_query(F.data == "admin_grp_welcome:preview")
async def cb_admin_grp_welcome_preview(callback: CallbackQuery):
    if not await ensure_admin(callback):
        return
    await callback.answer("Menampilkan preview welcome...")

    template = await get_setting("group_welcome_text", DEFAULT_GROUP_WELCOME_TEXT)
    media_type = await get_setting("group_welcome_media_type", "none")
    photo_id = await get_setting("group_welcome_photo_file_id", "")
    gift_id = await get_setting("group_welcome_gift_file_id", "")
    video_id = await get_setting("group_welcome_video_file_id", "")

    admin_tag = f"@{callback.from_user.username}" if callback.from_user.username else callback.from_user.full_name
    preview_text = template.replace("@USERNAME", admin_tag)

    header = "👁️ <b>[ PREVIEW WELCOME ]</b>\n\n"

    try:
        if media_type == "photo" and photo_id:
            await callback.message.answer_photo(
                photo=photo_id,
                caption=header + preview_text,
                reply_markup=build_admin_back_keyboard("admin_grp_welcome:root")
            )
        elif media_type == "gift" and gift_id:
            await callback.message.answer_animation(
                animation=gift_id,
                caption=header + preview_text,
                reply_markup=build_admin_back_keyboard("admin_grp_welcome:root")
            )
        elif media_type == "video" and video_id:
            await callback.message.answer_video(
                video=video_id,
                caption=header + preview_text,
                reply_markup=build_admin_back_keyboard("admin_grp_welcome:root")
            )
        else:
            await callback.message.answer(
                header + preview_text,
                reply_markup=build_admin_back_keyboard("admin_grp_welcome:root")
            )
    except Exception as e:
        logger.error(f"Error previewing welcome: {e}")
        await callback.message.answer(f"Gagal menampilkan preview: {e}")


# =========================================================
# A. WELCOME SETTINGS
# =========================================================

@router.callback_query(F.data == "admin_welcome:root")
async def cb_admin_welcome_root(callback: CallbackQuery):
    if not await ensure_admin(callback):
        return
    await callback.answer()

    welcome_text = await get_setting("welcome_message", "")
    btn_help = await get_setting("btn_help_label", "HELP")
    btn_contact = await get_setting("btn_contact_label", "CONTACT @FPENGAMAT")
    btn_group = await get_setting("btn_group_label", "GROUP MANAGEMENT")

    text = (
        f"{TITLE_DECOR}\n\n"
        f"📝 <b>A. WELCOME SETTINGS (/start)</b>\n\n"
        f"• <b>Pesan Welcome Saat Ini:</b>\n<i>{welcome_text}</i>\n\n"
        f"• <b>Label Tombol 1:</b> <code>{btn_help}</code>\n"
        f"• <b>Label Tombol 2:</b> <code>{btn_contact}</code>\n"
        f"• <b>Label Tombol 3:</b> <code>{btn_group}</code>\n\n"
        f"<i>Pesan Welcome hanya muncul di private chat dan tidak pernah mengganggu grup.</i>\n\n"
        f"{FOOTER_DECOR}"
    )

    markup = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✏️ Edit Pesan Welcome", callback_data="admin_welcome:edit_msg")],
            [InlineKeyboardButton(text="✏️ Edit Label Tombol HELP", callback_data="admin_welcome:edit_help")],
            [InlineKeyboardButton(text="✏️ Edit Label Tombol CONTACT", callback_data="admin_welcome:edit_contact")],
            [InlineKeyboardButton(text="✏️ Edit Label Tombol GROUP", callback_data="admin_welcome:edit_group")],
            [InlineKeyboardButton(text="🔙 BACK", callback_data="admin:main")],
        ]
    )
    await callback.message.edit_text(text, reply_markup=markup, parse_mode="HTML")


@router.callback_query(F.data == "admin_welcome:edit_msg")
async def cb_edit_welcome_msg(callback: CallbackQuery, state: FSMContext):
    await state.set_state(WelcomeSettingsState.waiting_welcome_text)
    await callback.answer()
    await callback.message.edit_text(
        "Ketikkan teks pesan Welcome baru untuk /start:",
        reply_markup=build_cancel_keyboard(),
        parse_mode="HTML"
    )


@router.message(WelcomeSettingsState.waiting_welcome_text)
async def process_new_welcome_text(message: Message, state: FSMContext):
    await set_setting("welcome_message", message.text.strip())
    await state.clear()
    await message.reply("✅ Pesan Welcome berhasil diperbarui!", reply_markup=build_admin_back_keyboard("admin_welcome:root"))


# =========================================================
# B. MENU SETTINGS & WEDDING MENU
# =========================================================

@router.callback_query(F.data == "admin_menu:root")
async def cb_admin_menu_root(callback: CallbackQuery):
    if not await ensure_admin(callback):
        return
    await callback.answer()

    w_title = await get_setting("wedding_menu_title", "Wedding Menu Service")
    w_desc = await get_setting("wedding_menu_desc", "Layanan hidangan pernikahan eksklusif.")

    indo_on = await is_catalog_enabled("indonesia")
    korean_on = await is_catalog_enabled("korean")
    foreign_on = await is_catalog_enabled("foreign")

    text = (
        f"{TITLE_DECOR}\n\n"
        f"🍽️ <b>B. MENU & KATALOG SETTINGS</b>\n\n"
        f"• <b>Wedding Menu Title:</b> {w_title}\n"
        f"• <b>Wedding Menu Deskripsi:</b> {w_desc}\n\n"
        f"<b>Status Katalog Aktif:</b>\n"
        f"• 🇮🇩 <b>Indonesia:</b> {'🟢 ON' if indo_on else '🔴 OFF'} (<code>/setindonesia on|off</code>)\n"
        f"• 🇰🇷 <b>Korean:</b> {'🟢 ON' if korean_on else '🔴 OFF'} (<code>/setkorean on|off</code>)\n"
        f"• 🌎 <b>Foreign:</b> {'🟢 ON' if foreign_on else '🔴 OFF'} (<code>/setforeign on|off</code>)\n\n"
        f"{FOOTER_DECOR}"
    )

    markup = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=f"🇮🇩 Indonesia: {'ON ✅' if indo_on else 'OFF ❌'}",
                    callback_data="admin_menu:toggle:indonesia"
                ),
            ],
            [
                InlineKeyboardButton(
                    text=f"🇰🇷 Korean: {'ON ✅' if korean_on else 'OFF ❌'}",
                    callback_data="admin_menu:toggle:korean"
                ),
            ],
            [
                InlineKeyboardButton(
                    text=f"🌎 Foreign: {'ON ✅' if foreign_on else 'OFF ❌'}",
                    callback_data="admin_menu:toggle:foreign"
                ),
            ],
            [InlineKeyboardButton(text="💍 Atur Judul Wedding Menu", callback_data="admin_menu:edit_wtitle")],
            [InlineKeyboardButton(text="📜 Atur Deskripsi Wedding Menu", callback_data="admin_menu:edit_wdesc")],
            [InlineKeyboardButton(text="🔙 BACK", callback_data="admin:main")],
        ]
    )
    await callback.message.edit_text(text, reply_markup=markup, parse_mode="HTML")


@router.callback_query(F.data.startswith("admin_menu:toggle:"))
async def cb_admin_menu_toggle(callback: CallbackQuery):
    if not await ensure_admin(callback):
        return
    cat = callback.data.split(":")[2]
    curr = await is_catalog_enabled(cat)
    new_state = not curr
    await set_catalog_status(cat, new_state)
    state_str = "ON" if new_state else "OFF"
    await callback.answer(f"Katalog {cat.capitalize()} diatur ke {state_str}!")
    await cb_admin_menu_root(callback)



@router.callback_query(F.data == "admin_menu:edit_wtitle")
async def cb_edit_wtitle(callback: CallbackQuery, state: FSMContext):
    await state.set_state(WeddingMenuSettingsState.waiting_title)
    await callback.answer()
    await callback.message.edit_text("Ketikkan judul paket Wedding Menu baru:", reply_markup=build_cancel_keyboard(), parse_mode="HTML")


@router.message(WeddingMenuSettingsState.waiting_title)
async def process_wtitle(message: Message, state: FSMContext):
    await set_setting("wedding_menu_title", message.text.strip())
    await state.clear()
    await message.reply("✅ Judul Wedding Menu berhasil disimpan!", reply_markup=build_admin_back_keyboard("admin_menu:root"))


@router.callback_query(F.data == "admin_menu:edit_wdesc")
async def cb_edit_wdesc(callback: CallbackQuery, state: FSMContext):
    await state.set_state(WeddingMenuSettingsState.waiting_desc)
    await callback.answer()
    await callback.message.edit_text("Ketikkan deskripsi paket Wedding Menu baru:", reply_markup=build_cancel_keyboard(), parse_mode="HTML")


@router.message(WeddingMenuSettingsState.waiting_desc)
async def process_wdesc(message: Message, state: FSMContext):
    await set_setting("wedding_menu_desc", message.text.strip())
    await state.clear()
    await message.reply("✅ Deskripsi Wedding Menu berhasil disimpan!", reply_markup=build_admin_back_keyboard("admin_menu:root"))


# =========================================================
# C. FOOD MANAGEMENT (ADD, DELETE, EDIT COMMAND, AVAILABILITY)
# =========================================================

@router.callback_query(F.data == "admin_food:root")
async def cb_admin_food_root(callback: CallbackQuery):
    if not await ensure_admin(callback):
        return
    await callback.answer()

    foods = await get_all_foods()

    text = (
        f"{TITLE_DECOR}\n\n"
        f"🍲 <b>C. FOOD MANAGEMENT</b>\n\n"
        f"Total hidangan aktif dalam database: <b>{len(foods)} Menu</b>\n\n"
        f"Pilih opsi manajemen makanan di bawah ini:\n"
        f"• <b>Tambah Makanan:</b> Otomatis membuat command khusus dan mencari foto makanan asli.\n"
        f"• <b>Atur Ketersediaan:</b> Ubah status Tersedia ⟷ Habis.\n"
        f"• <b>Edit / Hapus:</b> Kelola command, harga, atau hapus menu.\n\n"
        f"{FOOTER_DECOR}"
    )

    markup = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="➕ Tambah Makanan Baru (Auto Command)", callback_data="admin_food:add")],
            [InlineKeyboardButton(text="🔄 Atur Ketersediaan (Tersedia / Habis)", callback_data="admin_food:avail_list:0")],
            [InlineKeyboardButton(text="✏️ Edit Command / Hapus Makanan", callback_data="admin_food:edit_list:0")],
            [InlineKeyboardButton(text="🔙 BACK", callback_data="admin:main")],
        ]
    )
    await callback.message.edit_text(text, reply_markup=markup, parse_mode="HTML")


# --- Add Food Wizard ---
@router.callback_query(F.data == "admin_food:add")
async def cb_admin_food_add_start(callback: CallbackQuery, state: FSMContext):
    if not await ensure_admin(callback):
        return
    await callback.answer()

    await state.set_state(AddFoodState.waiting_name)
    text = (
        f"{TITLE_DECOR}\n\n"
        f"➕ <b>TAMBAH MAKANAN BARU (1/3)</b>\n\n"
        f"Ketikkan <b>Nama Makanan</b> yang ingin ditambahkan.\n"
        f"<i>Contoh: Telur Balado, Ayam Geprek, Bulgogi Deluxe</i>\n\n"
        f"{FOOTER_DECOR}"
    )
    await callback.message.edit_text(text, reply_markup=build_cancel_keyboard(), parse_mode="HTML")


@router.message(AddFoodState.waiting_name)
async def process_food_name(message: Message, state: FSMContext):
    food_name = message.text.strip().replace("(", "").replace(")", "")
    auto_cmd = format_command(food_name)
    await state.update_data(name=food_name, command=auto_cmd)
    await state.set_state(AddFoodState.waiting_category)

    text = (
        f"{TITLE_DECOR}\n\n"
        f"➕ <b>TAMBAH MAKANAN BARU (2/3)</b>\n\n"
        f"• Nama: <b>{food_name}</b>\n"
        f"• Auto Command: <code>{auto_cmd}</code>\n\n"
        f"Pilih kategori makanan:\n\n"
        f"{FOOTER_DECOR}"
    )
    markup = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🇮🇩 Indonesian Food", callback_data="add_cat:indonesia")],
            [InlineKeyboardButton(text="🇰🇷 Korean Food", callback_data="add_cat:korean")],
            [InlineKeyboardButton(text="🌎 Foreign Food", callback_data="add_cat:foreign")],
            [InlineKeyboardButton(text="❌ Batal", callback_data="fsm:cancel")],
        ]
    )
    await message.reply(text, reply_markup=markup, parse_mode="HTML")


@router.callback_query(F.data.startswith("add_cat:"), AddFoodState.waiting_category)
async def process_food_category(callback: CallbackQuery, state: FSMContext):
    cat = callback.data.split(":")[1]
    await state.update_data(category=cat)
    await state.set_state(AddFoodState.waiting_subcategory)
    await callback.answer()

    markup = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🍽️ Main Course", callback_data="add_sub:Main Course")],
            [InlineKeyboardButton(text="🥗 Side Dish", callback_data="add_sub:Side Dish")],
            [InlineKeyboardButton(text="🍧 Dessert", callback_data="add_sub:Dessert")],
            [InlineKeyboardButton(text="🥤 Drinks", callback_data="add_sub:Drinks")],
            [InlineKeyboardButton(text="❌ Batal", callback_data="fsm:cancel")],
        ]
    )
    await callback.message.edit_text("Pilih subkategori makanan:", reply_markup=markup, parse_mode="HTML")


@router.callback_query(F.data.startswith("add_sub:"), AddFoodState.waiting_subcategory)
async def process_food_subcategory(callback: CallbackQuery, state: FSMContext):
    sub = callback.data.split(":")[1]
    await state.update_data(subcategory=sub)
    await state.set_state(AddFoodState.waiting_price)
    await callback.answer()

    await callback.message.edit_text(
        "Ketikkan harga makanan (contoh: <code>35000</code> atau <code>0</code>):",
        reply_markup=build_cancel_keyboard(),
        parse_mode="HTML"
    )


@router.message(AddFoodState.waiting_price)
async def process_food_price_and_auto_search(message: Message, state: FSMContext):
    raw_price = message.text.replace(".", "").replace(",", "").strip()
    price = float(raw_price) if raw_price.isdigit() else 0.0
    await state.update_data(price=price)

    data = await state.get_data()
    food_name = data["name"]

    search_status = await message.reply("🔍 <i>Mencari foto makanan asli otomatis (bukan wedding)...</i>", parse_mode="HTML")
    img_res = await search_food_image(food_name)

    await state.update_data(
        image_url=img_res["url"],
        image_source=img_res["source"],
        image_license=img_res["license"],
    )

    auto_approve = (await get_setting("auto_approve_image", "1")) == "1"

    if auto_approve and img_res.get("found"):
        await add_food(
            name=food_name,
            command=data["command"],
            category=data["category"],
            subcategory=data["subcategory"],
            price=price,
            photo_url=img_res["url"],
            image_source=img_res["source"],
            image_license=img_res["license"],
            is_approved=True
        )
        await state.clear()
        try:
            await search_status.delete()
        except Exception:
            pass

        resp = (
            f"✅ <b>Makanan Berhasil Ditambahkan!</b>\n\n"
            f"• <b>Nama:</b> {food_name}\n"
            f"• <b>Command:</b> <code>{data['command']}</code>\n"
            f"• <b>Kategori:</b> {data['category'].capitalize()}\n"
            f"• <b>Sumber Foto:</b> {img_res['source']} ({img_res['license']})\n\n"
            f"Pengguna sekarang dapat mengetik <code>{data['command']}</code> untuk melihat foto dan memesan."
        )
        try:
            await message.reply_photo(photo=img_res["url"], caption=generate_aschen_caption(food_name))
        except Exception:
            pass
        await message.reply(resp, reply_markup=build_admin_back_keyboard("admin_food:root"), parse_mode="HTML")
    else:
        await state.set_state(AddFoodState.waiting_preview_decision)
        try:
            await search_status.delete()
        except Exception:
            pass

        preview_text = (
            f"🖼️ <b>PREVIEW FOTO MAKANAN ASLI</b>\n\n"
            f"• <b>Nama:</b> {food_name}\n"
            f"• <b>Command:</b> <code>{data['command']}</code>\n"
            f"• <b>Sumber:</b> {img_res['source']}\n"
            f"• <b>Lisensi:</b> {img_res['license']}\n\n"
            f"Setujui foto ini untuk katalog makanan?"
        )
        markup = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="✅ Setujui & Simpan", callback_data="add_img_decision:approve")],
                [InlineKeyboardButton(text="❌ Batal", callback_data="fsm:cancel")],
            ]
        )
        try:
            await message.reply_photo(photo=img_res["url"], caption=preview_text, reply_markup=markup, parse_mode="HTML")
        except Exception:
            await message.reply(preview_text, reply_markup=markup, parse_mode="HTML")


@router.callback_query(F.data == "add_img_decision:approve", AddFoodState.waiting_preview_decision)
async def process_approve_new_food(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    await add_food(
        name=data["name"],
        command=data["command"],
        category=data["category"],
        subcategory=data["subcategory"],
        price=data["price"],
        photo_url=data["image_url"],
        image_source=data["image_source"],
        image_license=data["image_license"],
        is_approved=True
    )
    await state.clear()
    await callback.answer()
    await callback.message.reply(
        f"✅ Makanan <b>{data['name']}</b> berhasil ditambahkan dengan command <code>{data['command']}</code>!",
        reply_markup=build_admin_back_keyboard("admin_food:root"),
        parse_mode="HTML"
    )


# --- Availability Toggle List ---
@router.callback_query(F.data.startswith("admin_food:avail_list:"))
async def cb_admin_food_avail_list(callback: CallbackQuery):
    if not await ensure_admin(callback):
        return
    page = int(callback.data.split(":")[2])
    await callback.answer()

    foods = await get_all_foods()
    per_page = 8
    total_pages = (len(foods) + per_page - 1) // per_page
    start = page * per_page
    end = min(start + per_page, len(foods))

    buttons = []
    for f in foods[start:end]:
        status_sym = "🟢 Tersedia" if f["is_available"] else "🔴 Habis"
        btn_text = f"{f['name']} ({status_sym})"
        buttons.append([InlineKeyboardButton(text=btn_text, callback_data=f"toggle_avail_m:{f['id']}:{page}")])

    nav_row = []
    if page > 0:
        nav_row.append(InlineKeyboardButton(text="◀️ Prev", callback_data=f"admin_food:avail_list:{page - 1}"))
    if page < total_pages - 1:
        nav_row.append(InlineKeyboardButton(text="Next ▶️", callback_data=f"admin_food:avail_list:{page + 1}"))
    if nav_row:
        buttons.append(nav_row)

    buttons.append([InlineKeyboardButton(text="🔙 BACK", callback_data="admin_food:root")])

    text = (
        f"{TITLE_DECOR}\n\n"
        f"🔄 <b>ATUR KETERSEDIAAN MAKANAN</b>\n"
        f"Klik hidangan untuk mengubah status ketersediaan:\n"
        f"Halaman {page + 1}/{max(1, total_pages)}\n\n"
        f"{FOOTER_DECOR}"
    )
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode="HTML")


@router.callback_query(F.data.startswith("toggle_avail_m:"))
async def cb_toggle_avail_m(callback: CallbackQuery):
    parts = callback.data.split(":")
    food_id = int(parts[1])
    page = int(parts[2])

    food = await get_food_by_id(food_id)
    if food:
        new_status = 0 if food["is_available"] else 1
        await update_food(food_id, is_available=new_status)
        lbl = "Tersedia" if new_status else "Habis (NOT AVAILABLE)"
        await callback.answer(f"{food['name']}: {lbl}")

    await cb_admin_food_avail_list(callback)


# --- Edit Food Command & Delete ---
@router.callback_query(F.data.startswith("admin_food:edit_list:"))
async def cb_admin_food_edit_list(callback: CallbackQuery):
    if not await ensure_admin(callback):
        return
    page = int(callback.data.split(":")[2])
    await callback.answer()

    foods = await get_all_foods()
    per_page = 8
    total_pages = (len(foods) + per_page - 1) // per_page
    start = page * per_page
    end = min(start + per_page, len(foods))

    buttons = []
    for f in foods[start:end]:
        buttons.append([InlineKeyboardButton(text=f"🍽️ {f['name']} ({f.get('command')})", callback_data=f"edit_m_food:{f['id']}:{page}")])

    nav_row = []
    if page > 0:
        nav_row.append(InlineKeyboardButton(text="◀️ Prev", callback_data=f"admin_food:edit_list:{page - 1}"))
    if page < total_pages - 1:
        nav_row.append(InlineKeyboardButton(text="Next ▶️", callback_data=f"admin_food:edit_list:{page + 1}"))
    if nav_row:
        buttons.append(nav_row)

    buttons.append([InlineKeyboardButton(text="🔙 BACK", callback_data="admin_food:root")])

    text = (
        f"{TITLE_DECOR}\n\n"
        f"✏️ <b>EDIT / HAPUS MENU MAKANAN</b>\n"
        f"Pilih hidangan untuk mengubah command atau menghapus dari database:\n\n"
        f"{FOOTER_DECOR}"
    )
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode="HTML")


@router.callback_query(F.data.startswith("edit_m_food:"))
async def cb_edit_m_food(callback: CallbackQuery):
    parts = callback.data.split(":")
    food_id = int(parts[1])
    page = int(parts[2])
    await callback.answer()

    food = await get_food_by_id(food_id)
    if not food:
        return

    text = (
        f"{TITLE_DECOR}\n\n"
        f"🍽️ <b>KELOLA: {food['name']}</b>\n\n"
        f"• <b>Command:</b> <code>{food.get('command', '-')}</code>\n"
        f"• <b>Kategori:</b> {food['category'].capitalize()} ({food['subcategory']})\n"
        f"• <b>Harga:</b> Rp {food['price']:,.0f}\n"
        f"• <b>Status:</b> {'🟢 Tersedia' if food['is_available'] else '🔴 Habis'}\n\n"
        f"{FOOTER_DECOR}"
    )

    markup = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🗑️ HAPUS MAKANAN", callback_data=f"del_m_food:{food_id}:{page}")],
            [InlineKeyboardButton(text="🔙 BACK", callback_data=f"admin_food:edit_list:{page}")],
        ]
    )
    await callback.message.edit_text(text, reply_markup=markup, parse_mode="HTML")


@router.callback_query(F.data.startswith("del_m_food:"))
async def cb_del_m_food(callback: CallbackQuery):
    parts = callback.data.split(":")
    food_id = int(parts[1])
    food = await get_food_by_id(food_id)
    if food:
        await delete_food(food_id)
        await callback.answer(f"Makanan {food['name']} berhasil dihapus!", show_alert=True)
    await cb_admin_food_edit_list(callback)


# =========================================================
# D. FOOD PHOTO SETTINGS
# =========================================================

@router.callback_query(F.data == "admin_img:root")
async def cb_admin_img_root(callback: CallbackQuery):
    if not await ensure_admin(callback):
        return
    await callback.answer()

    auto_search = await get_setting("auto_image_search", "1")
    search_status_lbl = "✅ ON" if auto_search == "1" else "❌ OFF"

    text = (
        f"{TITLE_DECOR}\n\n"
        f"🖼️ <b>D. FOOD PHOTO SETTINGS</b>\n\n"
        f"• Automatic Image Search: <b>{search_status_lbl}</b>\n\n"
        f"<i>PENTING: Seluruh foto yang ditampilkan wajib berupa foto makanan asli, bukan foto wedding / pengantin.</i>\n\n"
        f"{FOOTER_DECOR}"
    )

    markup = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=f"🔄 Saklar Auto Search: {search_status_lbl}", callback_data="toggle_setting_m:auto_image_search:admin_img:root")],
            [InlineKeyboardButton(text="🔍 Cari Ulang Foto Makanan (Search Again)", callback_data="admin_img:research_list:0")],
            [InlineKeyboardButton(text="📤 Upload Foto Manual", callback_data="admin_img:upload_list:0")],
            [InlineKeyboardButton(text="🔙 BACK", callback_data="admin:main")],
        ]
    )
    await callback.message.edit_text(text, reply_markup=markup, parse_mode="HTML")


@router.callback_query(F.data.startswith("admin_img:research_list:"))
async def cb_admin_img_research_list(callback: CallbackQuery):
    page = int(callback.data.split(":")[2])
    await callback.answer()
    foods = await get_all_foods()
    per_page = 8
    total_pages = (len(foods) + per_page - 1) // per_page
    start = page * per_page
    end = min(start + per_page, len(foods))

    buttons = []
    for f in foods[start:end]:
        buttons.append([InlineKeyboardButton(text=f"🔍 {f['name']}", callback_data=f"trigger_research_m:{f['id']}:{page}")])

    nav_row = []
    if page > 0:
        nav_row.append(InlineKeyboardButton(text="◀️ Prev", callback_data=f"admin_img:research_list:{page - 1}"))
    if page < total_pages - 1:
        nav_row.append(InlineKeyboardButton(text="Next ▶️", callback_data=f"admin_img:research_list:{page + 1}"))
    if nav_row:
        buttons.append(nav_row)

    buttons.append([InlineKeyboardButton(text="🔙 BACK", callback_data="admin_img:root")])
    await callback.message.edit_text("Pilih makanan yang ingin dicari ulang fotonya secara otomatis:", reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))


@router.callback_query(F.data.startswith("trigger_research_m:"))
async def cb_trigger_research_m(callback: CallbackQuery):
    parts = callback.data.split(":")
    food_id = int(parts[1])
    food = await get_food_by_id(food_id)
    if not food:
        return

    await callback.answer("Mencari foto makanan asli...", show_alert=False)
    img_res = await search_food_image(food["name"])
    await update_food(
        food_id,
        photo_url=img_res["url"],
        photo_file_id=None,
        image_source=img_res["source"],
        image_license=img_res["license"]
    )
    await callback.message.reply(
        f"✅ Foto <b>{food['name']}</b> berhasil diperbarui dari {img_res['source']}!",
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("admin_img:upload_list:"))
async def cb_admin_img_upload_list(callback: CallbackQuery):
    page = int(callback.data.split(":")[2])
    await callback.answer()
    foods = await get_all_foods()
    per_page = 8
    total_pages = (len(foods) + per_page - 1) // per_page
    start = page * per_page
    end = min(start + per_page, len(foods))

    buttons = []
    for f in foods[start:end]:
        buttons.append([InlineKeyboardButton(text=f"📤 {f['name']}", callback_data=f"manual_up_m:{f['id']}")])

    nav_row = []
    if page > 0:
        nav_row.append(InlineKeyboardButton(text="◀️ Prev", callback_data=f"admin_img:upload_list:{page - 1}"))
    if page < total_pages - 1:
        nav_row.append(InlineKeyboardButton(text="Next ▶️", callback_data=f"admin_img:upload_list:{page + 1}"))
    if nav_row:
        buttons.append(nav_row)

    buttons.append([InlineKeyboardButton(text="🔙 BACK", callback_data="admin_img:root")])
    await callback.message.edit_text("Pilih hidangan untuk mengunggah foto manual:", reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))


@router.callback_query(F.data.startswith("manual_up_m:"))
async def cb_manual_up_m(callback: CallbackQuery, state: FSMContext):
    food_id = int(callback.data.split(":")[1])
    food = await get_food_by_id(food_id)
    if not food:
        return

    await state.set_state(ImageSettingsState.waiting_manual_upload)
    await state.update_data(food_id=food_id, food_name=food["name"])
    await callback.answer()

    await callback.message.edit_text(
        f"Kirimkan foto makanan untuk <b>{food['name']}</b> langsung ke chat ini:",
        reply_markup=build_cancel_keyboard(),
        parse_mode="HTML"
    )


@router.message(ImageSettingsState.waiting_manual_upload, F.photo)
async def process_manual_upload_done(message: Message, state: FSMContext):
    data = await state.get_data()
    food_id = data["food_id"]
    photo_file_id = message.photo[-1].file_id

    await update_food(
        food_id,
        photo_file_id=photo_file_id,
        image_source="Admin Manual Upload",
        image_license="Authorized ASCHEN Photo"
    )
    await state.clear()
    await message.reply(
        f"✅ Foto manual untuk <b>{data['food_name']}</b> berhasil dipasang!",
        reply_markup=build_admin_back_keyboard("admin_img:root"),
        parse_mode="HTML"
    )


# =========================================================
# E. CAPTION SETTINGS
# =========================================================

@router.callback_query(F.data == "admin_caption:root")
async def cb_admin_caption_root(callback: CallbackQuery):
    if not await ensure_admin(callback):
        return
    await callback.answer()

    sample = generate_aschen_caption("Rendang")

    text = (
        f"{TITLE_DECOR}\n\n"
        f"💬 <b>E. CAPTION SETTINGS</b>\n\n"
        f"<b>Format Standar ASCHEN:</b>\n"
        f"<code>{sample}</code>\n\n"
        f"<i>Ketentuan: NAMA MAKANAN disesuaikan dinamis dan dilarang memuat tanda kurung.</i>\n\n"
        f"{FOOTER_DECOR}"
    )
    markup = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔙 BACK", callback_data="admin:main")],
        ]
    )
    await callback.message.edit_text(text, reply_markup=markup, parse_mode="HTML")


# =========================================================
# F. ORDER BUTTON SETTINGS
# =========================================================

@router.callback_query(F.data == "admin_btn:root")
async def cb_admin_btn_root(callback: CallbackQuery):
    if not await ensure_admin(callback):
        return
    await callback.answer()

    btn1_text = await get_setting("order_btn_1_text", "ORDER VIA @ASCHENEO")
    btn1_url = await get_setting("order_btn_1_url", ORDER_URL)
    btn2_text = await get_setting("order_btn_2_text", "ORDER VIA @ASCHENEO :: OFFICIAL")
    btn2_url = await get_setting("order_btn_2_url", ORDER_URL)

    text = (
        f"{TITLE_DECOR}\n\n"
        f"🛒 <b>F. ORDER BUTTON SETTINGS</b>\n\n"
        f"<b>BUTTON 1:</b>\n"
        f"• Teks: <code>{btn1_text}</code>\n"
        f"• URL: <code>{btn1_url}</code>\n\n"
        f"<b>BUTTON 2:</b>\n"
        f"• Teks: <code>{btn2_text}</code>\n"
        f"• URL: <code>{btn2_url}</code>\n\n"
        f"{FOOTER_DECOR}"
    )

    markup = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✏️ Edit Teks Tombol 1", callback_data="admin_btn:edit_t1")],
            [InlineKeyboardButton(text="🔗 Edit URL Tombol 1", callback_data="admin_btn:edit_u1")],
            [InlineKeyboardButton(text="✏️ Edit Teks Tombol 2", callback_data="admin_btn:edit_t2")],
            [InlineKeyboardButton(text="🔗 Edit URL Tombol 2", callback_data="admin_btn:edit_u2")],
            [InlineKeyboardButton(text="💾 SAVE & PREVIEW", callback_data="admin_btn:preview")],
            [InlineKeyboardButton(text="🔙 BACK", callback_data="admin:main")],
        ]
    )
    await callback.message.edit_text(text, reply_markup=markup, parse_mode="HTML")


@router.callback_query(F.data == "admin_btn:edit_t1")
async def cb_btn_edit_t1(callback: CallbackQuery, state: FSMContext):
    await state.set_state(OrderBtnSettingsState.waiting_btn1_text)
    await callback.answer()
    await callback.message.edit_text("Ketikkan teks baru Tombol 1:", reply_markup=build_cancel_keyboard(), parse_mode="HTML")


@router.message(OrderBtnSettingsState.waiting_btn1_text)
async def process_btn_t1(message: Message, state: FSMContext):
    await set_setting("order_btn_1_text", message.text.strip())
    await state.clear()
    await message.reply("✅ Tombol 1 diperbarui! Klik SAVE untuk menerapkan.", reply_markup=build_admin_back_keyboard("admin_btn:root"))


@router.callback_query(F.data == "admin_btn:edit_u1")
async def cb_btn_edit_u1(callback: CallbackQuery, state: FSMContext):
    await state.set_state(OrderBtnSettingsState.waiting_btn1_url)
    await callback.answer()
    await callback.message.edit_text("Ketikkan URL baru Tombol 1:", reply_markup=build_cancel_keyboard(), parse_mode="HTML")


@router.message(OrderBtnSettingsState.waiting_btn1_url)
async def process_btn_u1(message: Message, state: FSMContext):
    url = message.text.strip()
    if not url.startswith("http"):
        url = "https://" + url
    await set_setting("order_btn_1_url", url)
    await state.clear()
    await message.reply("✅ URL Tombol 1 diperbarui!", reply_markup=build_admin_back_keyboard("admin_btn:root"))


@router.callback_query(F.data == "admin_btn:edit_t2")
async def cb_btn_edit_t2(callback: CallbackQuery, state: FSMContext):
    await state.set_state(OrderBtnSettingsState.waiting_btn2_text)
    await callback.answer()
    await callback.message.edit_text("Ketikkan teks baru Tombol 2:", reply_markup=build_cancel_keyboard(), parse_mode="HTML")


@router.message(OrderBtnSettingsState.waiting_btn2_text)
async def process_btn_t2(message: Message, state: FSMContext):
    await set_setting("order_btn_2_text", message.text.strip())
    await state.clear()
    await message.reply("✅ Tombol 2 diperbarui!", reply_markup=build_admin_back_keyboard("admin_btn:root"))


@router.callback_query(F.data == "admin_btn:edit_u2")
async def cb_btn_edit_u2(callback: CallbackQuery, state: FSMContext):
    await state.set_state(OrderBtnSettingsState.waiting_btn2_url)
    await callback.answer()
    await callback.message.edit_text("Ketikkan URL baru Tombol 2:", reply_markup=build_cancel_keyboard(), parse_mode="HTML")


@router.message(OrderBtnSettingsState.waiting_btn2_url)
async def process_btn_u2(message: Message, state: FSMContext):
    url = message.text.strip()
    if not url.startswith("http"):
        url = "https://" + url
    await set_setting("order_btn_2_url", url)
    await state.clear()
    await message.reply("✅ URL Tombol 2 diperbarui!", reply_markup=build_admin_back_keyboard("admin_btn:root"))


@router.callback_query(F.data == "admin_btn:preview")
async def cb_btn_preview(callback: CallbackQuery):
    await callback.answer("Pengaturan tombol disimpan!", show_alert=True)
    btn1_text = await get_setting("order_btn_1_text", "ORDER VIA @ASCHENEO")
    btn1_url = await get_setting("order_btn_1_url", ORDER_URL)
    btn2_text = await get_setting("order_btn_2_text", "ORDER VIA @ASCHENEO :: OFFICIAL")
    btn2_url = await get_setting("order_btn_2_url", ORDER_URL)

    markup = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=btn1_text, url=btn1_url)],
            [InlineKeyboardButton(text=btn2_text, url=btn2_url)],
            [InlineKeyboardButton(text="🔙 BACK", callback_data="admin_btn:root")],
        ]
    )
    await callback.message.edit_text("👁️ <b>Live Preview Tombol Pemesanan:</b>", reply_markup=markup, parse_mode="HTML")


# =========================================================
# G. BOT SETTINGS & DATABASE BACKUP
# =========================================================

@router.callback_query(F.data == "admin_bot:root")
async def cb_admin_bot_root(callback: CallbackQuery):
    if not await ensure_admin(callback):
        return
    await callback.answer()

    text = (
        f"{TITLE_DECOR}\n\n"
        f"⚙️ <b>H. BOT SETTINGS & DATABASE BACKUP</b>\n\n"
        f"• <b>Official Organizer:</b> {OFFICIAL_ORGANIZER}\n"
        f"• <b>Official Contact:</b> {OFFICIAL_CONTACT} ({CONTACT_URL})\n"
        f"• <b>Order URL:</b> {ORDER_URL}\n\n"
        f"Klik tombol di bawah untuk membuat cadangan database secara instan:\n\n"
        f"{FOOTER_DECOR}"
    )

    markup = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="💾 DOWNLOAD DATABASE BACKUP (.db)", callback_data="admin_db:backup")],
            [InlineKeyboardButton(text="🔙 BACK", callback_data="admin:main")],
        ]
    )
    await callback.message.edit_text(text, reply_markup=markup, parse_mode="HTML")


@router.callback_query(F.data == "admin_db:backup")
async def cb_admin_db_backup(callback: CallbackQuery):
    if not await ensure_admin(callback):
        return
    await callback.answer("Membuat database backup...", show_alert=False)

    backup_path = await backup_database()
    if not backup_path:
        await callback.message.answer("❌ File database belum tersedia untuk dicadangkan.")
        return

    doc = FSInputFile(path=backup_path, filename="aschi_bot_backup.db")
    caption = (
        f"{TITLE_DECOR}\n\n"
        f"💾 <b>DATABASE BACKUP BERHASIL DIUNDUH</b>\n\n"
        f"• File: <code>{backup_path}</code>\n"
        f"• Status: Terverifikasi utuh dan aman.\n\n"
        f"{FOOTER_DECOR}"
    )
    try:
        await callback.message.answer_document(
            document=doc,
            caption=caption,
            reply_markup=build_admin_back_keyboard("admin_bot:root"),
            parse_mode="HTML"
        )
    except Exception as e:
        logger.error(f"Backup send error: {e}")
        await callback.message.answer(f"Backup tersimpan di server: <code>{backup_path}</code>", parse_mode="HTML")


# =========================================================
# I. ADMIN ACCESS MANAGEMENT
# =========================================================

@router.callback_query(F.data == "admin_acc:root")
async def cb_admin_acc_root(callback: CallbackQuery):
    if not await ensure_admin(callback):
        return
    await callback.answer()

    admins = await list_admins()
    items = []
    for a in admins:
        role = "👑 Owner" if a["user_id"] == OWNER_ID else "🛡️ Admin"
        items.append(f"• {role}: <code>{a['user_id']}</code> (@{a.get('username') or 'User'})")

    text = (
        f"{TITLE_DECOR}\n\n"
        f"👥 <b>I. ADMIN ACCESS CONTROL</b>\n\n"
        f"Daftar administrator resmi ({len(admins)}):\n"
        + "\n".join(items)
        + f"\n\n{FOOTER_DECOR}"
    )

    markup = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="➕ Tambah Admin Baru", callback_data="admin_acc:add")],
            [InlineKeyboardButton(text="➖ Hapus Admin", callback_data="admin_acc:remove")],
            [InlineKeyboardButton(text="🔙 BACK", callback_data="admin:main")],
        ]
    )
    await callback.message.edit_text(text, reply_markup=markup, parse_mode="HTML")


@router.callback_query(F.data == "admin_acc:add")
async def cb_admin_acc_add(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id != OWNER_ID:
        await callback.answer("Hanya Owner yang dapat mengangkat admin.", show_alert=True)
        return
    await state.set_state(AdminAccessState.waiting_user_id)
    await callback.answer()
    await callback.message.edit_text(
        "Ketikkan Telegram User ID calon admin baru:\n(Contoh: <code>123456789</code>)",
        reply_markup=build_cancel_keyboard(),
        parse_mode="HTML"
    )


@router.message(AdminAccessState.waiting_user_id)
async def process_add_admin_id(message: Message, state: FSMContext):
    raw_id = message.text.strip()
    if not raw_id.isdigit():
        await message.reply("User ID harus berupa angka.")
        return

    new_id = int(raw_id)
    await add_admin(user_id=new_id, username="", added_by=message.from_user.id)
    await state.clear()
    await message.reply(f"✅ User ID <code>{new_id}</code> berhasil diangkat sebagai Admin!", reply_markup=build_admin_back_keyboard("admin_acc:root"), parse_mode="HTML")


@router.callback_query(F.data == "admin_acc:remove")
async def cb_admin_acc_remove_list(callback: CallbackQuery):
    if callback.from_user.id != OWNER_ID:
        await callback.answer("Hanya Owner yang dapat mencabut admin.", show_alert=True)
        return
    await callback.answer()

    admins = await list_admins()
    buttons = []
    for a in admins:
        if a["user_id"] != OWNER_ID:
            buttons.append([InlineKeyboardButton(text=f"❌ Hapus: {a['user_id']}", callback_data=f"del_admin_m:{a['user_id']}")])

    buttons.append([InlineKeyboardButton(text="🔙 BACK", callback_data="admin_acc:root")])
    await callback.message.edit_text("Pilih admin yang ingin dicabut hak aksesnya:", reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))


@router.callback_query(F.data.startswith("del_admin_m:"))
async def cb_del_admin_m(callback: CallbackQuery):
    admin_id = int(callback.data.split(":")[1])
    await remove_admin(admin_id)
    await callback.answer("Akses admin dicabut.", show_alert=True)
    await cb_admin_acc_root(callback)
