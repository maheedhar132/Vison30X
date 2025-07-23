import os
import json
import random
import logging
from datetime import datetime
from dotenv import load_dotenv
import textwrap

# Load .env variables
load_dotenv()
CHAT_ID = int(os.getenv("CHAT_ID", "0"))

# Logging configuration
LOG_DIR = "/var/log/vision30x"
os.makedirs(LOG_DIR, exist_ok=True)
logging.basicConfig(
    filename=os.path.join(LOG_DIR, "bot.log"),
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

# File path setup
DATA_PATH = os.path.dirname(__file__)
CARDS_FILE = os.path.join(DATA_PATH, "data", "cards.json")

def load_cards():
    try:
        with open(CARDS_FILE, encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logging.error(f"Failed to load cards: {e}")
        return []

def wrap_text_block(text, width):
    lines = textwrap.wrap(text, width)
    return [line.ljust(width) for line in lines]

def calculate_dynamic_width(title, message, reflection, base_width=42, padding=4):
    candidates = (
        [title]
        + textwrap.wrap(message, base_width)
        + textwrap.wrap(reflection, base_width)
        + ["Reflect:"]
    )
    max_line = max((len(line) for line in candidates), default=base_width)
    return max(base_width, min(max_line + padding, 80))

# Cache for daily picked card
_cached_card_day = None
_cached_card = None

async def send_card_prompt(app):
    global _cached_card_day, _cached_card

    try:
        today = datetime.now().date()

        # Only pick once per day
        if _cached_card_day != today:
            cards = load_cards()
            if not cards:
                await app.bot.send_message(CHAT_ID, "❌ No cards found.")
                return

            _cached_card = random.choice(cards)
            _cached_card_day = today
            logging.info(f"Card picked: {json.dumps(_cached_card, indent=2)}")

        app.bot_data["chosen_card"] = _cached_card

        print(f"[DEBUG] Card picked: {_cached_card.get('title', 'N/A')}")
        print(f"[DEBUG] Full card: {json.dumps(_cached_card, indent=2)}")

        await app.bot.send_message(CHAT_ID, "🃏 A new affirmation card has been drawn. Reflect on your day.")

    except Exception as e:
        logging.error(f"Failed to send card prompt: {e}")
        await app.bot.send_message(CHAT_ID, "❌ Failed to send card prompt.")

async def send_card_reveal(app):
    try:
        chosen = app.bot_data.get("chosen_card")

        if not chosen:
            await app.bot.send_message(CHAT_ID, "⚠️ No card drawn yet. Use /force_card first.")
            return

        title = chosen.get("title", "").strip()
        message_text = chosen.get("message", "").strip()
        reflection = chosen.get("reflection") or chosen.get("prompt", "")
        reflection = reflection.strip()

        if not all([title, message_text, reflection]):
            raise ValueError("Missing one or more required card fields: title, message, reflection/prompt")

        box_width = 30
        border = "─" * (box_width + 2)

        # Strip emoji from the start and store separately
        message_emoji = message_text[0] if ord(message_text[0]) > 127 else ""
        reflection_emoji = reflection[0] if ord(reflection[0]) > 127 else ""

        message_clean = message_text[1:].strip() if message_emoji else message_text
        reflection_clean = reflection[1:].strip() if reflection_emoji else reflection

        message_lines = wrap_text_block(message_clean, box_width)
        reflection_lines = wrap_text_block(reflection_clean, box_width)

        card_lines = [
            f"┌{border}┐",
            f"│ {'🌟 YOUR CARD TODAY'.center(box_width)} │",
            f"├{border}┤",
            f"│ 🔖 {title.ljust(box_width - 3)} │",
            f"├{border}┤",
        ]

        # Emoji on its own line for message block
        if message_emoji:
            card_lines.append(f"{message_emoji}")
        for line in message_lines:
            card_lines.append(f"│ {line} │")

        card_lines.append(f"├{border}┤")

        # Emoji on its own line for reflection block
        if reflection_emoji:
            card_lines.append(f"{reflection_emoji}")
        for line in reflection_lines:
            card_lines.append(f"│ {line} │")

        card_lines.append(f"└{border}┘")

        card_text = "\n".join(card_lines)

        logging.info(f"Card revealed: {title}")
        print(f"[DEBUG] Revealed card:\n{card_text}")
        await app.bot.send_message(CHAT_ID, card_text)

    except Exception as e:
        logging.exception("Failed to reveal card")
        print(f"[ERROR] Reveal failed: {e}")
        await app.bot.send_message(CHAT_ID, "❌ Failed to reveal card.")
