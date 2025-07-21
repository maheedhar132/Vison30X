import os, json, random
from dotenv import load_dotenv

load_dotenv()
CHAT_ID = int(os.getenv("CHAT_ID"))

DATA_PATH = os.path.join(os.path.dirname(__file__), "data")
MANIFEST_FILE = os.path.join(DATA_PATH, "manifestations.json")
USED_FILE = os.path.join(DATA_PATH, "used_manifest_ids.json")

def load_manifestations():
    with open(MANIFEST_FILE) as f:
        return json.load(f)

def get_used_ids():
    if not os.path.exists(USED_FILE):
        return []
    with open(USED_FILE) as f:
        return json.load(f)

def save_used_id(mid):
    used = get_used_ids()
    used.append(mid)
    with open(USED_FILE, "w") as f:
        json.dump(used, f)

def pick_new_manifest():
    all_m = load_manifestations()
    used = get_used_ids()
    available = [m for m in all_m if m["id"] not in used]
    if not available:
        return random.choice(all_m)  # fallback: reuse
    chosen = random.choice(available)
    save_used_id(chosen["id"])
    return chosen

def send_manifestation(app, index):
    manifest = app.bot_data.get("today_manifest")
    if not manifest:
        manifest = pick_new_manifest()
        app.bot_data["today_manifest"] = manifest
    if manifest:
        app.bot.send_message(CHAT_ID, text=f"🌅 Manifestation:\n\n{manifest['set'][index]}")
