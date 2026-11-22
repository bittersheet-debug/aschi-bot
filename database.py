"""
ASCHI BOT — DATABASE MODULE (SQLite with aiosqlite)
ASCHEN EVENT ORGANIZER
Manages Users, Groups, Moderation Logs, Wedding Foods with Commands, Settings, and Admin permissions.
"""

import re
import aiosqlite
from datetime import datetime
from typing import List, Dict, Any, Optional
from config import (
    DB_PATH,
    OWNER_ID,
    DEFAULT_ORDER_BTN_1_TEXT,
    DEFAULT_ORDER_BTN_1_URL,
    DEFAULT_ORDER_BTN_2_TEXT,
    DEFAULT_ORDER_BTN_2_URL,
    CONTACT_URL,
)


def format_command(raw_name: str) -> str:
    """Formats a food name into a valid Telegram command like /telur or /ayam_bakar."""
    clean = re.sub(r"[^a-zA-Z0-9_]", "_", raw_name.strip().lower())
    clean = re.sub(r"_+", "_", clean).strip("_")
    return f"/{clean}"


async def init_db():
    """Initializes tables, migrations, and default settings."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("PRAGMA foreign_keys = ON")

        # Users table
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                full_name TEXT,
                joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        # Groups table
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS groups (
                group_id INTEGER PRIMARY KEY,
                title TEXT,
                is_active INTEGER DEFAULT 1,
                is_bot_admin INTEGER DEFAULT 0,
                can_restrict_members INTEGER DEFAULT 0,
                can_delete_messages INTEGER DEFAULT 0,
                joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        # Moderation Logs table
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS moderation_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                group_id INTEGER,
                admin_id INTEGER,
                admin_name TEXT,
                user_id INTEGER,
                user_name TEXT,
                action TEXT,
                reason TEXT,
                duration TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        # Foods table with command column
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS foods (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                command TEXT UNIQUE,
                category TEXT NOT NULL,
                subcategory TEXT,
                description TEXT,
                price REAL DEFAULT 0.0,
                is_available INTEGER DEFAULT 1,
                sort_order INTEGER DEFAULT 0,
                photo_file_id TEXT,
                photo_url TEXT,
                image_source TEXT,
                image_license TEXT,
                custom_caption TEXT,
                is_approved INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        # Check and add 'command' column if missing in older schema
        try:
            async with db.execute("PRAGMA table_info(foods)") as cursor:
                columns = [row[1] for row in await cursor.fetchall()]
                if "command" not in columns:
                    await db.execute("ALTER TABLE foods ADD COLUMN command TEXT")
        except Exception:
            pass

        # Settings table
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            )
            """
        )

        # Admins table
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS admins (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                added_by INTEGER,
                can_manage_menu INTEGER DEFAULT 1,
                can_manage_images INTEGER DEFAULT 1,
                can_manage_buttons INTEGER DEFAULT 1,
                can_manage_moderation INTEGER DEFAULT 1,
                can_manage_settings INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        # Default settings populate
        default_settings = {
            "order_btn_1_text": DEFAULT_ORDER_BTN_1_TEXT,
            "order_btn_1_url": DEFAULT_ORDER_BTN_1_URL,
            "order_btn_2_text": DEFAULT_ORDER_BTN_2_TEXT,
            "order_btn_2_url": DEFAULT_ORDER_BTN_2_URL,
            "auto_image_search": "1",
            "auto_approve_image": "1",
            "mod_ban_enabled": "1",
            "mod_mute_enabled": "1",
            "mod_kick_enabled": "1",
            "mod_unban_enabled": "1",
            "mod_unmute_enabled": "1",
            "welcome_enabled": "1",
            "welcome_message": "Welcome to ASCHI BOT — Official Assistant of ASCHEN EVENT ORGANIZER.\n\nThank you for using ASCHI BOT. Please select the service below.",
            "btn_help_label": "HELP",
            "btn_contact_label": "CONTACT @FPENGAMAT",
            "btn_contact_url": CONTACT_URL,
            "btn_group_label": "GROUP MANAGEMENT",
            "wedding_menu_title": "Wedding Menu Service",
            "wedding_menu_desc": "Layanan hidangan pernikahan eksklusif dari ASCHEN EVENT ORGANIZER.",
        }

        for key, value in default_settings.items():
            await db.execute(
                "INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)",
                (key, value)
            )

        # Add OWNER_ID as super admin if provided
        if OWNER_ID:
            await db.execute(
                """
                INSERT OR IGNORE INTO admins 
                (user_id, username, added_by, can_manage_menu, can_manage_images, can_manage_buttons, can_manage_moderation, can_manage_settings)
                VALUES (?, ?, ?, 1, 1, 1, 1, 1)
                """,
                (OWNER_ID, "Owner", 0)
            )

        await db.commit()


# ---------------- USER FUNCTIONS ----------------
async def register_user(user_id: int, username: Optional[str], full_name: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            INSERT INTO users (user_id, username, full_name, joined_at)
            VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(user_id) DO UPDATE SET
                username = excluded.username,
                full_name = excluded.full_name
            """,
            (user_id, username or "", full_name)
        )
        await db.commit()


# ---------------- GROUP FUNCTIONS ----------------
async def update_group_status(
    group_id: int,
    title: str,
    is_active: bool = True,
    is_bot_admin: bool = False,
    can_restrict_members: bool = False,
    can_delete_messages: bool = False
):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            INSERT INTO groups (group_id, title, is_active, is_bot_admin, can_restrict_members, can_delete_messages, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(group_id) DO UPDATE SET
                title = excluded.title,
                is_active = excluded.is_active,
                is_bot_admin = excluded.is_bot_admin,
                can_restrict_members = excluded.can_restrict_members,
                can_delete_messages = excluded.can_delete_messages,
                updated_at = CURRENT_TIMESTAMP
            """,
            (
                group_id,
                title,
                1 if is_active else 0,
                1 if is_bot_admin else 0,
                1 if can_restrict_members else 0,
                1 if can_delete_messages else 0
            )
        )
        await db.commit()


async def get_group(group_id: int) -> Optional[Dict[str, Any]]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM groups WHERE group_id = ?", (group_id,)) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None


# ---------------- MODERATION LOGS ----------------
async def log_moderation(
    group_id: int,
    admin_id: int,
    admin_name: str,
    user_id: int,
    user_name: str,
    action: str,
    reason: str,
    duration: str = "-"
):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            INSERT INTO moderation_logs 
            (group_id, admin_id, admin_name, user_id, user_name, action, reason, duration, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """,
            (group_id, admin_id, admin_name, user_id, user_name, action, reason, duration)
        )
        await db.commit()


async def get_recent_moderation_logs(limit: int = 15) -> List[Dict[str, Any]]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM moderation_logs ORDER BY id DESC LIMIT ?", (limit,)
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]


# ---------------- FOODS CRUD ----------------
async def get_foods_by_category(category: str, subcategory: Optional[str] = None) -> List[Dict[str, Any]]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        if subcategory:
            query = "SELECT * FROM foods WHERE category = ? AND subcategory = ? ORDER BY sort_order ASC, id ASC"
            params = (category, subcategory)
        else:
            query = "SELECT * FROM foods WHERE category = ? ORDER BY sort_order ASC, id ASC"
            params = (category,)

        async with db.execute(query, params) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]


async def get_food_by_id(food_id: int) -> Optional[Dict[str, Any]]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM foods WHERE id = ?", (food_id,)) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None


async def get_food_by_command(command: str) -> Optional[Dict[str, Any]]:
    """Fetches food by its exact command, e.g. '/telur' or 'telur'."""
    cmd = command.strip().lower()
    if not cmd.startswith("/"):
        cmd = f"/{cmd}"
    # Strip any bot username suffix if present like /rendang@ASCHIASCHENBOT
    if "@" in cmd:
        cmd = cmd.split("@")[0]

    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM foods WHERE LOWER(command) = ?", (cmd,)) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None


async def get_all_food_commands() -> List[str]:
    """Returns a list of all registered food commands."""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT command FROM foods WHERE command IS NOT NULL") as cursor:
            rows = await cursor.fetchall()
            return [row[0].lower() for row in rows if row[0]]


async def add_food(
    name: str,
    category: str,
    command: Optional[str] = None,
    subcategory: str = "Main Course",
    description: str = "",
    price: float = 0.0,
    photo_url: str = "",
    photo_file_id: Optional[str] = None,
    image_source: str = "Automatic Search",
    image_license: str = "Standard/Public",
    custom_caption: Optional[str] = None,
    is_available: bool = True,
    is_approved: bool = True
) -> int:
    cmd = command or format_command(name)
    if not cmd.startswith("/"):
        cmd = f"/{cmd}"

    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            """
            INSERT INTO foods (
                name, command, category, subcategory, description, price, is_available,
                photo_file_id, photo_url, image_source, image_license,
                custom_caption, is_approved, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """,
            (
                name,
                cmd,
                category,
                subcategory,
                description,
                price,
                1 if is_available else 0,
                photo_file_id,
                photo_url,
                image_source,
                image_license,
                custom_caption,
                1 if is_approved else 0
            )
        )
        await db.commit()
        return cursor.lastrowid


async def update_food(food_id: int, **kwargs) -> bool:
    if not kwargs:
        return False
    fields = []
    values = []
    for key, val in kwargs.items():
        fields.append(f"{key} = ?")
        values.append(val)
    fields.append("updated_at = CURRENT_TIMESTAMP")
    values.append(food_id)

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            f"UPDATE foods SET {', '.join(fields)} WHERE id = ?",
            tuple(values)
        )
        await db.commit()
        return True


async def update_food_file_id(food_id: int, photo_file_id: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE foods SET photo_file_id = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (photo_file_id, food_id)
        )
        await db.commit()


async def delete_food(food_id: int) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM foods WHERE id = ?", (food_id,))
        await db.commit()
        return True


async def get_all_foods() -> List[Dict[str, Any]]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM foods ORDER BY category, subcategory, id") as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]


# ---------------- SETTINGS ----------------
async def get_setting(key: str, default: str = "") -> str:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT value FROM settings WHERE key = ?", (key,)) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else default


async def set_setting(key: str, value: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO settings (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, value)
        )
        await db.commit()


async def get_all_settings() -> Dict[str, str]:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT key, value FROM settings") as cursor:
            rows = await cursor.fetchall()
            return {row[0]: row[1] for row in rows}


# ---------------- ADMIN MANAGEMENT ----------------
async def is_admin_or_owner(user_id: int) -> bool:
    if OWNER_ID and user_id == OWNER_ID:
        return True
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT user_id FROM admins WHERE user_id = ?", (user_id,)) as cursor:
            row = await cursor.fetchone()
            return bool(row)


async def get_admin(user_id: int) -> Optional[Dict[str, Any]]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM admins WHERE user_id = ?", (user_id,)) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None


async def add_admin(user_id: int, username: str, added_by: int) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            INSERT INTO admins (user_id, username, added_by)
            VALUES (?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET username = excluded.username
            """,
            (user_id, username, added_by)
        )
        await db.commit()
        return True


async def remove_admin(user_id: int) -> bool:
    if OWNER_ID and user_id == OWNER_ID:
        return False
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM admins WHERE user_id = ?", (user_id,))
        await db.commit()
        return True


async def list_admins() -> List[Dict[str, Any]]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM admins ORDER BY created_at ASC") as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]


# ---------------- DATABASE BACKUP ----------------
async def backup_database() -> Optional[str]:
    """Creates a timestamped copy of the database in backups/ directory."""
    import shutil
    import os
    from pathlib import Path

    if not os.path.exists(DB_PATH):
        return None

    backup_dir = Path("backups")
    backup_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = backup_dir / f"aschi_backup_{timestamp}.db"

    try:
        shutil.copy2(DB_PATH, backup_file)
        return str(backup_file)
    except Exception:
        return None
