import os
import json
import random
import logging
import textwrap
from dotenv import load_dotenv
from telegram import constants

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
DATA_PATH = os.path.join(os.path.dirname(__file__), "data")
CARDS_FILE = os.path.join(DATA_PATH, "cards.json")

def load_cards():
    try:
        with open(CARDS_FILE, encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logging.error(f"Failed to load cards: {e}")
        return []

async def send_card_prompt(app):
    try:
        cards = load_cards()
        if not cards:
            await app.bot.send_message(CHAT_ID, "❌ No cards found.")
            return

        chosen = random.choice(cards)
        app.bot_data["chosen_card"] = chosen
        logging.info(f"Card picked: {chosen['title']}")

        await app.bot.send_message(CHAT_ID, "🃏 A new affirmation card has been drawn. Reflect on your day.")
    except Exception as e:
        logging.error(f"Failed to send card prompt: {e}")
        await app.bot.send_message(CHAT_ID, "❌ Failed to send card prompt.")

def wrap_text_block(text, width=42, max_lines=5):
    lines = textwrap.wrap(text.strip(), width=width)
    if len(lines) > max_lines:
        lines = lines[:max_lines - 1] + ['...']
    return [line.ljust(width) for line in lines]

async def send_card_reveal(app):
    try:
        chosen = app.bot_data.get("chosen_card")
        if not chosen:
            await app.bot.send_message(CHAT_ID, "⚠️ No card drawn yet. Use /force_card first.")
            return

        title = chosen["title"].strip()
        message_text = chosen["message"].strip()
        reflection = chosen["reflection"].strip()

        message_lines = wrap_text_block(message_text)
        reflection_lines = wrap_text_block(reflection)

        card_lines = [
            "┌────────────────────────────────────────────┐",
            "│              YOUR CARD TODAY              │",
            "├────────────────────────────────────────────┤",
            f"│ {title.center(42)} │",
            "├────────────────────────────────────────────┤",
        ]
        for line in message_lines:
            card_lines.append(f"│ {line} │")
        card_lines.append("├────────────────────────────────────────────┤")
        card_lines.append("│ Reflect:                                   │")
        for line in reflection_lines:
            card_lines.append(f"│ {line} │")
        card_lines.append("└────────────────────────────────────────────┘")

        card_text = "\n".join(card_lines)

        await app.bot.send_message(CHAT_ID, card_text)
        logging.info(f"Card revealed: {title}")
    except Exception as e:
        logging.exception("Failed to reveal card")
        await app.bot.send_message(CHAT_ID, "❌ Failed to reveal card.")
