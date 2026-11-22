"""
ASCHI BOT — INTERACTIVE FOOD CAPTION ENGINE
ASCHEN EVENT ORGANIZER
Strict formatting according to ASCHEN brand guidelines:
- No parentheses allowed
- Exact decorative typography preserved
- Interactive roleplay text maintained
- Dynamic food name insertion
- NO automatic descriptions, explanations, or extra text added. Exact admin caption only.
"""

from config import TITLE_DECOR, FOOTER_DECOR


def generate_aschen_caption(food_name: str, custom_caption: str = None) -> str:
    """
    Generate the official ASCHEN interactive food caption.
    Strict constraint: NEVER use parentheses '(' or ')'.
    Uses the exact caption without automatic descriptions or extra information.
    """
    clean_name = food_name.replace("(", "").replace(")", "").strip()

    if custom_caption:
        # Sanitize any parentheses from custom captions
        return custom_caption.replace("(", "").replace(")", "").strip()

    return (
        f"{TITLE_DECOR}\n\n"
        f"/mengangguk ; Senyum ; mengambil makanan {clean_name}\n\n"
        f"Bonjour! Hello! Ini makanan {clean_name}, mau pesan apa lagi? Please mention the name of the food.\n\n"
        f"/senyum manis ; letakkan {clean_name} ; di atas meja\n\n"
        f"{FOOTER_DECOR}"
    )
