import json, random, os
from datetime import datetime

CHAT_ID = int(os.getenv("CHAT_ID"))

def load_manifest():
    with open("data/manifest_log.json") as f:
        return json.load(f)

def get_used_ids():
    if not os.path.exists("data/used_ids.json"):
        return []
    with open("data/used_ids.json") as f:
        return json.load(f)

def save_used_id(id):
    used = get_used_ids()
    used.append(id)
    with open("data/used_ids.json", "w") as f:
        json.dump(used, f)

def pick_new_manifest():
    all_manifests = load_manifest()
    used_ids = get_used_ids()
    options = [m for m in all_manifests if m["id"] not in used_ids]
    if not options:
        print("Manifest pool exhausted!")
        return None
    chosen = random.choice(options)
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
