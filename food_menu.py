"""
ASCHI BOT — WEDDING FOOD MENU & PHOTO GALLERY
ASCHEN EVENT ORGANIZER
Strict Compliance with PROMPT FIX FINAL & PERBAIKAN FOTO MENU DAN KATEGORI MINUMAN:
- Category commands: /Indonesia, /Korean, /Foreign
- Displays strictly: Makanan, Dessert, Minuman for all 3 categories!
- No Main Course, No Side Dish, No List Menu, No navigation buttons (BACK, NEXT, HOME).
- Under each food photo: ONLY the Two Order Buttons in separate rows.
- Pure authentic food & drink photography (never wedding photos!).
- Guaranteed photo delivery (URL + BufferedInputFile fallback).
"""

import aiohttp
import logging
from typing import Optional, List, Dict, Any
from aiogram import Router, F
from aiogram.types import Message, BufferedInputFile
from aiogram.filters import Command
from config import (
    TITLE_DECOR,
    FOOTER_DECOR,
    IMAGE_NOT_FOUND_URL,
)
from database import (
    get_foods_by_category,
    get_food_by_id,
    update_food_file_id,
    is_catalog_enabled,
    set_catalog_status,
    get_active_catalogs,
    is_admin_or_owner,
)
from captions import generate_aschen_caption
from keyboards import build_food_order_keyboard

logger = logging.getLogger(__name__)
router = Router(name="food_menu")


# ---------------- CATEGORY COMMAND HANDLERS ----------------

async def generate_category_command_list(category: str) -> str:
    """
    Generates clean command list grouped strictly into:
    - Makanan
    - Dessert
    - Minuman
    All 3 categories (Indonesia, Korean, Foreign) have these sections.
    """
    foods = await get_foods_by_category(category)

    makanan_items = [f for f in foods if f.get("subcategory") == "Makanan"]
    dessert_items = [f for f in foods if f.get("subcategory") == "Dessert"]
    minuman_items = [f for f in foods if f.get("subcategory") == "Minuman"]

    title_map = {
        "indonesia": "INDONESIAN FOOD 🇮🇩",
        "korean": "KOREAN FOOD 🇰🇷",
        "foreign": "FOREIGN FOOD 🌎",
    }
    cat_title = title_map.get(category, "FOOD MENU")

    lines = [
        TITLE_DECOR,
        "",
        f"<b>{cat_title}</b>",
        "<i>Daftar Command Menu</i>",
        "",
    ]

    if makanan_items:
        lines.append("🍽️ <b>Makanan</b>")
        for f in makanan_items:
            lines.append(f"• {f['command']} — {f['name']}")
        lines.append("")

    if dessert_items:
        lines.append("🍧 <b>Dessert</b>")
        for f in dessert_items:
            lines.append(f"• {f['command']} — {f['name']}")
        lines.append("")

    if minuman_items:
        lines.append("🥤 <b>Minuman</b>")
        for f in minuman_items:
            lines.append(f"• {f['command']} — {f['name']}")
        lines.append("")

    lines.append(FOOTER_DECOR)
    return "\n".join(lines)


# ---------------- MENU OVERVIEW COMMAND (/menu) ----------------

@router.message(Command("menu", ignore_case=True))
@router.message(Command("menuaschi", ignore_case=True))
async def cmd_menu(message: Message):
    """
    Displays list of currently active catalogs.
    If all catalogs are OFF, displays: 'Saat ini katalog belum tersedia.'
    Example format when active:
    - Indonesia
    - Korean
    """
    active = await get_active_catalogs()
    if not active:
        await message.reply("Saat ini katalog belum tersedia.")
        return

    name_map = {
        "indonesia": "Indonesia",
        "korean": "Korean",
        "foreign": "Foreign",
    }

    lines = [f"- {name_map.get(cat, cat.capitalize())}" for cat in active]
    await message.reply("\n".join(lines))


# ---------------- CATEGORY COMMAND HANDLERS ----------------

@router.message(Command("indonesia", ignore_case=True))
async def cmd_indonesia(message: Message):
    """Displays Indonesian Food commands grouped by Makanan, Dessert, Minuman."""
    if not await is_catalog_enabled("indonesia"):
        await message.reply("Maaf, katalog ini sedang tidak tersedia.")
        return
    text = await generate_category_command_list("indonesia")
    await message.reply(text, parse_mode="HTML")


@router.message(Command("korean", ignore_case=True))
async def cmd_korean(message: Message):
    """Displays Korean Food commands grouped by Makanan, Dessert, Minuman."""
    if not await is_catalog_enabled("korean"):
        await message.reply("Maaf, katalog ini sedang tidak tersedia.")
        return
    text = await generate_category_command_list("korean")
    await message.reply(text, parse_mode="HTML")


@router.message(Command("foreign", ignore_case=True))
async def cmd_foreign(message: Message):
    """Displays Foreign Food commands grouped by Makanan, Dessert, Minuman."""
    if not await is_catalog_enabled("foreign"):
        await message.reply("Maaf, katalog ini sedang tidak tersedia.")
        return
    text = await generate_category_command_list("foreign")
    await message.reply(text, parse_mode="HTML")


# ---------------- ADMIN CATALOG CONTROL COMMANDS ----------------

async def process_set_catalog_command(message: Message, category: str, display_name: str):
    """
    Handles /setindonesia on|off, /setkorean on|off, /setforeign on|off.
    Restricted to authorized admins only.
    Non-admins receive: 'Access Denied — Admin Only.'
    """
    if not await is_admin_or_owner(message.from_user.id):
        await message.reply("Access Denied — Admin Only.")
        return

    args = message.text.split()[1:] if message.text else []
    if not args or args[0].lower() not in ["on", "off"]:
        curr_status = "ON" if await is_catalog_enabled(category) else "OFF"
        await message.reply(
            f"Format command: <code>/set{category} on</code> atau <code>/set{category} off</code>\n"
            f"Status katalog {display_name} saat ini: <b>{curr_status}</b>",
            parse_mode="HTML"
        )
        return

    action = args[0].lower()
    new_state = (action == "on")
    await set_catalog_status(category, new_state)
    status_label = "diaktifkan (ON)" if new_state else "dinonaktifkan (OFF)"
    await message.reply(f"Katalog {display_name} berhasil {status_label}.")


@router.message(Command("setindonesia", ignore_case=True))
async def cmd_set_indonesia(message: Message):
    """Admin command to turn Indonesia catalog on or off."""
    await process_set_catalog_command(message, "indonesia", "Indonesia")


@router.message(Command("setkorean", ignore_case=True))
async def cmd_set_korean(message: Message):
    """Admin command to turn Korean catalog on or off."""
    await process_set_catalog_command(message, "korean", "Korea")


@router.message(Command("setforeign", ignore_case=True))
async def cmd_set_foreign(message: Message):
    """Admin command to turn Foreign catalog on or off."""
    await process_set_catalog_command(message, "foreign", "Foreign")



# ---------------- PHOTO CARD RENDERER ----------------

async def send_food_item_card(
    bot,
    chat_id: int,
    food: Dict[str, Any]
):
    """
    Renders food/drink photo strictly:
    - Pure authentic food/drink photo
    - Exact ASCHEN caption (or admin custom caption)
    - NO automatic descriptions or extra information
    - Two Order Buttons in separate rows
    - NO BACK, NO NEXT, NO HOME, NO other navigation buttons
    - Resilient delivery via URL or direct buffer
    """
    caption_text = generate_aschen_caption(
        food_name=food["name"],
        custom_caption=food.get("custom_caption")
    )

    markup = await build_food_order_keyboard()

    # Step 1: If Telegram file_id is cached, send directly (instant!)
    if food.get("photo_file_id"):
        try:
            await bot.send_photo(
                chat_id=chat_id,
                photo=food["photo_file_id"],
                caption=caption_text,
                reply_markup=markup
            )
            return
        except Exception as e:
            logger.debug(f"Cached file_id send failed for {food['name']}: {e}")

    # Step 2: Send using URL
    photo_url = food.get("photo_url") or IMAGE_NOT_FOUND_URL
    try:
        sent = await bot.send_photo(
            chat_id=chat_id,
            photo=photo_url,
            caption=caption_text,
            reply_markup=markup
        )
        if sent.photo:
            await update_food_file_id(food["id"], sent.photo[-1].file_id)
        return
    except Exception as e:
        logger.warning(f"URL photo send failed for {food['name']}: {e}, downloading buffer fallback...")

    # Step 3: Buffered download fallback (guarantees photo is delivered)
    try:
        async with aiohttp.ClientSession() as session:
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}
            async with session.get(photo_url, headers=headers, timeout=aiohttp.ClientTimeout(total=8)) as resp:
                if resp.status == 200:
                    image_bytes = await resp.read()
                    buffered_photo = BufferedInputFile(image_bytes, filename=f"{food['name'].replace(' ', '_')}.jpg")
                    sent = await bot.send_photo(
                        chat_id=chat_id,
                        photo=buffered_photo,
                        caption=caption_text,
                        reply_markup=markup
                    )
                    if sent.photo:
                        await update_food_file_id(food["id"], sent.photo[-1].file_id)
                    return
    except Exception as err:
        logger.error(f"Buffered photo fallback also failed for {food['name']}: {err}")

    # Step 4: Fallback to verified image URL
    try:
        sent = await bot.send_photo(
            chat_id=chat_id,
            photo=IMAGE_NOT_FOUND_URL,
            caption=caption_text,
            reply_markup=markup
        )
        if sent.photo:
            await update_food_file_id(food["id"], sent.photo[-1].file_id)
    except Exception as final_err:
        logger.error(f"Final photo send failed: {final_err}")
