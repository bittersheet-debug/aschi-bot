"""
ASCHI BOT — COMPREHENSIVE TEST SUITE (PERBAIKAN FOTO & MINUMAN)
Tests all core systems:
- Category command lists (Makanan, Dessert, Minuman for all 3 cuisines)
- All 87 food and drink items
- Indonesian Minuman (/es_teh_manis, /es_jeruk, etc.)
- Direct Food & Drink Commands
- Captions (No parentheses, exact admin caption, no automatic descriptions)
- Keyboards (Under photo: ONLY 2 order buttons; NO BACK, NEXT, HOME)
- Food photos (Strictly pure food photos, HTTP 200)
- /maurits access control
"""

import asyncio
import os
import unittest
from datetime import timedelta

# Set temporary test database
os.environ["DB_PATH"] = "test_aschi_v3.db"
os.environ["OWNER_ID"] = "999999999"

import database
from captions import generate_aschen_caption
from seed_data import seed_database, INITIAL_FOOD_ITEMS
from image_search import search_food_image
from keyboards import (
    build_start_keyboard,
    build_food_order_keyboard,
)
from moderation import format_user_tag, get_admin_tag
from admin_dashboard import DENIED_TEXT
from food_menu import generate_category_command_list


class TestAschiBotV3(unittest.IsolatedAsyncioTestCase):

    async def asyncSetUp(self):
        await database.init_db()

    async def asyncTearDown(self):
        if os.path.exists("test_aschi_v3.db"):
            try:
                os.remove("test_aschi_v3.db")
            except Exception:
                pass

    # 1. Test Database & Direct Food & Drink Commands (Total 87 Items)
    async def test_database_and_drinks(self):
        await seed_database()
        foods = await database.get_all_foods()
        self.assertEqual(len(foods), len(INITIAL_FOOD_ITEMS))
        self.assertEqual(len(foods), 87)

        # Check subcategories are ONLY Makanan, Dessert, Minuman
        subcats = set(f["subcategory"] for f in foods)
        self.assertEqual(subcats, {"Makanan", "Dessert", "Minuman"})
        self.assertNotIn("Main Course", subcats)
        self.assertNotIn("Side Dish", subcats)

        # Check Indonesian drinks
        indo_drinks = [f for f in foods if f["category"] == "indonesia" and f["subcategory"] == "Minuman"]
        self.assertEqual(len(indo_drinks), 5)
        indo_cmds = [f["command"] for f in indo_drinks]
        self.assertIn("/es_teh_manis", indo_cmds)
        self.assertIn("/es_jeruk", indo_cmds)

        # Check Korean drinks
        korean_drinks = [f for f in foods if f["category"] == "korean" and f["subcategory"] == "Minuman"]
        self.assertEqual(len(korean_drinks), 4)

        # Check Foreign drinks
        foreign_drinks = [f for f in foods if f["category"] == "foreign" and f["subcategory"] == "Minuman"]
        self.assertEqual(len(foreign_drinks), 5)

    # 2. Test Category Command List Text (All 3 have Makanan, Dessert, Minuman)
    async def test_category_command_lists_with_drinks(self):
        await seed_database()

        # Indonesian list MUST have Makanan, Dessert, Minuman
        indo_text = await generate_category_command_list("indonesia")
        self.assertIn("Makanan", indo_text)
        self.assertIn("Dessert", indo_text)
        self.assertIn("Minuman", indo_text)
        self.assertIn("/es_teh_manis", indo_text)
        self.assertIn("/telur", indo_text)

        # Korean list MUST have Makanan, Dessert, Minuman
        korean_text = await generate_category_command_list("korean")
        self.assertIn("Makanan", korean_text)
        self.assertIn("Dessert", korean_text)
        self.assertIn("Minuman", korean_text)
        self.assertIn("/bulgogi", korean_text)
        self.assertIn("/strawberry_milk", korean_text)

        # Foreign list MUST have Makanan, Dessert, Minuman
        foreign_text = await generate_category_command_list("foreign")
        self.assertIn("Makanan", foreign_text)
        self.assertIn("Dessert", foreign_text)
        self.assertIn("Minuman", foreign_text)
        self.assertIn("/pizza", foreign_text)
        self.assertIn("/lemonade", foreign_text)

    # 3. Test Food Photo Keyboard (ONLY TWO ORDER BUTTONS: NO BACK, NEXT, HOME)
    async def test_food_order_keyboard_no_navigation(self):
        kb = await build_food_order_keyboard()
        buttons = [btn for row in kb.inline_keyboard for btn in row]
        self.assertEqual(len(buttons), 2)  # Exactly 2 buttons!

        btn_texts = [b.text for b in buttons]
        self.assertIn("ORDER VIA @ASCHENEO", btn_texts)
        self.assertIn("ORDER VIA @ASCHENEO :: OFFICIAL", btn_texts)

        for txt in btn_texts:
            self.assertNotIn("BACK", txt.upper())
            self.assertNotIn("NEXT", txt.upper())
            self.assertNotIn("HOME", txt.upper())

    # 4. Test Caption Constraints (No Parentheses, Exact Roleplay, No Auto-Descriptions)
    def test_caption_constraints(self):
        caption = generate_aschen_caption("Es Teh Manis")

        self.assertNotIn("(", caption)
        self.assertNotIn(")", caption)
        self.assertIn("Es Teh Manis", caption)
        self.assertIn("/mengangguk ; Senyum ; mengambil makanan", caption)
        self.assertIn("@ASCHENEO", caption)

    # 5. Test Food Photos (Strictly Food & Drink, Found=True)
    async def test_food_photos(self):
        drinks = ["Es Teh Manis", "Strawberry Milk", "Lemonade", "Rendang", "Pizza"]
        for d in drinks:
            res = await search_food_image(d)
            self.assertTrue(res["found"])
            self.assertIn("http", res["url"])

    # 6. Test /maurits Access Control
    async def test_maurits_access(self):
        self.assertTrue(await database.is_admin_or_owner(999999999))
        self.assertFalse(await database.is_admin_or_owner(123456789))
        self.assertEqual(DENIED_TEXT, "ACCESS DENIED. ADMIN ONLY.")

    # 7. Test Muted Members Tracking in Database
    async def test_muted_members_tracking(self):
        group_id = -100123456789
        user_id = 555666777

        # Initially not muted
        self.assertFalse(await database.is_member_muted(group_id, user_id))

        # Mute user
        await database.set_member_muted(group_id, user_id, 999999999, "@AdminMaurits")
        self.assertTrue(await database.is_member_muted(group_id, user_id))

        rec = await database.get_muted_record(group_id, user_id)
        self.assertIsNotNone(rec)
        self.assertEqual(rec["admin_name"], "@AdminMaurits")

        # Unmute user
        await database.set_member_unmuted(group_id, user_id)
        self.assertFalse(await database.is_member_muted(group_id, user_id))

    # 8. Test User Registration and Lookup for Moderation (@username & numeric ID)
    async def test_user_resolution_and_registration(self):
        await database.register_user(111222, "JohnDoe", "John Doe")

        by_un = await database.get_user_by_username("johndoe")
        self.assertIsNotNone(by_un)
        self.assertEqual(by_un["user_id"], 111222)

        by_un_at = await database.get_user_by_username("@johndoe")
        self.assertIsNotNone(by_un_at)
        self.assertEqual(by_un_at["user_id"], 111222)

        by_id = await database.get_user_by_id(111222)
        self.assertIsNotNone(by_id)
        self.assertEqual(by_id["username"], "JohnDoe")

    # 9. Test Group Welcome Settings and Template
    async def test_group_welcome_settings(self):
        # Default welcome text check
        default_text = await database.get_setting("group_welcome_text", database.DEFAULT_GROUP_WELCOME_TEXT)
        self.assertIn("𓄲 𓂃 𝐖𝐄𝐋𝐂𝐎𝐌𝐄, @USERNAME 𓂃", default_text)
        self.assertIn("𓆩 𝐀𝐒𝐂𝐇𝐄𝐍 𓆪", default_text)

        # Duration setting check (default 5s)
        duration = await database.get_setting("group_welcome_duration", "5")
        self.assertEqual(duration, "5")

        # Replacement test
        replaced = default_text.replace("@USERNAME", "@new_member")
        self.assertIn("@new_member", replaced)
        self.assertNotIn("@USERNAME", replaced)

    # 10. Test Welcome Management Keyboard
    def test_welcome_mgmt_keyboard(self):
        from keyboards import build_welcome_mgmt_keyboard
        kb = build_welcome_mgmt_keyboard(is_enabled=True, media_type="photo")
        buttons = [btn for row in kb.inline_keyboard for btn in row]
        button_texts = [b.text for b in buttons]

        self.assertIn("🔴 Disable Welcome", button_texts)
        self.assertIn("📝 Welcome Text", button_texts)
        self.assertIn("🖼️ Welcome Photo", button_texts)
        self.assertIn("🎁 Welcome Gift", button_texts)
        self.assertIn("📹 Welcome Video", button_texts)
        self.assertIn("⏱️ Welcome Duration", button_texts)
        self.assertIn("👁️ Preview Welcome", button_texts)



if __name__ == "__main__":
    unittest.main()
