import os
import json
import random
import logging
from dotenv import load_dotenv
from telegram import constants

# Load chat ID
load_dotenv()
CHAT_ID = int(os.getenv("CHAT_ID", "0"))

# Logging setup
LOG_DIR = "/var/log/vision30x"
os.makedirs(LOG_DIR, exist_ok=True)
logging.basicConfig(
    filename=os.path.join(LOG_DIR, "bot.log"),
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

# File path
DATA_PATH = os.path.join(os.path.dirname(__file__), "data")
CARDS_FILE = os.path.join(DATA_PATH, "cards.json")

def load_cards():
    try:
        with open(CARDS_FILE) as f:
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

async def send_card_reveal(app):
    try:
        chosen = app.bot_data.get("chosen_card")
        if not chosen:
            await app.bot.send_message(CHAT_ID, "❌ No card has been picked yet.")
            return

        text = (
            f"🔮 *Your Card Today:*\n\n"
            f"*{chosen['title']}*\n\n"
            f"_{chosen['message']}_\n\n"
            f"*Reflect:* {chosen['reflection']}"
        )
        await app.bot.send_message(CHAT_ID, text, parse_mode=constants.ParseMode.MARKDOWN)
        logging.info(f"Card revealed: {chosen['title']}")
    except Exception as e:
        logging.error(f"Failed to send card reveal: {e}")
        await app.bot.send_message(CHAT_ID, "❌ Failed to reveal card.")
