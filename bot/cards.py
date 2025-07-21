import os, json, random
from dotenv import load_dotenv

load_dotenv()
CHAT_ID = int(os.getenv("CHAT_ID"))

DATA_PATH = os.path.join(os.path.dirname(__file__), "data")
CARD_FILE = os.path.join(DATA_PATH, "cards.json")

def load_cards():
    with open(CARD_FILE) as f:
        return json.load(f)

def send_card_prompt(app):
    app.bot_data["chosen_card"] = None
    app.bot.send_message(CHAT_ID, text=(
        "🃏 Your card is ready...\n\n──────────────\n     [ 🂠 ]\n──────────────\n\n"
        "Reveal it at 7:00 PM tonight. Stay focused till then."
    ))

def send_card_reveal(app):
    card = app.bot_data.get("chosen_card")
    if not card:
        cards = load_cards()
        card = random.choice(cards)
        app.bot_data["chosen_card"] = card

    app.bot.send_message(CHAT_ID, text=(
        f"✨ Your Card: {card['title']}\n\n"
        "━━━━━━━━━━━━━━━\n"
        f"{card['message']}\n"
        "━━━━━━━━━━━━━━━\n\n"
        f"📝 Reflect:\n{card['prompt']}"
    ))
