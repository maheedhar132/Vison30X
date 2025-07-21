import os
import json
import random
from datetime import datetime

# Load CHAT_ID safely
chat_id_raw = os.getenv("CHAT_ID")
if not chat_id_raw:
    raise RuntimeError("CHAT_ID not set in .env")
CHAT_ID = int(chat_id_raw)

# ----------- Manifestation System ------------

def load_manifest():
    with open("data/manifest_log.json") as f:
        return json.load(f)

def get_used_ids():
    path = "data/used_ids.json"
    if not os.path.exists(path):
        return []
    with open(path) as f:
        return json.load(f)

def save_used_id(manifest_id):
    used = get_used_ids()
    used.append(manifest_id)
    with open("data/used_ids.json", "w") as f:
        json.dump(used, f)

def pick_new_manifest():
    all_manifests = load_manifest()
    used_ids = get_used_ids()
    unused = [m for m in all_manifests if m["id"] not in used_ids]
    if not unused:
        print("⚠️ Manifestation pool exhausted!")
        return None
    chosen = random.choice(unused)
    save_used_id(chosen["id"])
    return chosen

def send_manifestation(app, index):
    manifest = app.bot_data.get("today_manifest")
    if not manifest:
        manifest = pick_new_manifest()
        app.bot_data["today_manifest"] = manifest

    if manifest:
        msg = manifest["set"][index]
        app.bot.send_message(chat_id=CHAT_ID, text=f"🌅 Morning Manifestation:\n\n{msg}")

# ----------- Card System ------------

def send_card_prompt(app):
    app.bot_data["chosen_card"] = None
    prompt_msg = (
        "🃏 Your card for today is ready.\n\n"
        "──────────────\n"
        "     [ 🂠 ]\n"
        "──────────────\n\n"
        "You'll reveal it tonight at 7 PM IST."
    )
    app.bot.send_message(chat_id=CHAT_ID, text=prompt_msg)

def send_card_reveal(app):
    if "chosen_card" not in app.bot_data or app.bot_data["chosen_card"] is None:
        with open("data/card_templates.json") as f:
            cards = json.load(f)
        chosen = random.choice(cards)
        app.bot_data["chosen_card"] = chosen
    else:
        chosen = app.bot_data["chosen_card"]

    card_text = (
        f"✨ Your Card: {chosen['title']}\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"{chosen['message']}\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        f"📝 Reflection Prompt:\n{chosen['prompt']}"
    )
    app.bot.send_message(chat_id=CHAT_ID, text=card_text)
