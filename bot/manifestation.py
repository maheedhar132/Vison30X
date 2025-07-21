import os
import json
import random
import logging
from dotenv import load_dotenv

# Load .env values
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

# File paths
DATA_PATH = os.path.join(os.path.dirname(__file__), "data")
MANIFEST_FILE = os.path.join(DATA_PATH, "manifestations.json")
USED_FILE = os.path.join(DATA_PATH, "used_manifest_ids.json")

def load_manifestations():
    try:
        with open(MANIFEST_FILE) as f:
            return json.load(f)
    except Exception as e:
        logging.error(f"Failed to load manifestations: {e}")
        return []

def get_used_ids():
    if not os.path.exists(USED_FILE):
        return []
    try:
        with open(USED_FILE) as f:
            return json.load(f)
    except Exception as e:
        logging.error(f"Failed to read used_manifest_ids.json: {e}")
        return []

def save_used_id(mid):
    try:
        used = get_used_ids()
        used.append(mid)
        with open(USED_FILE, "w") as f:
            json.dump(used, f)
    except Exception as e:
        logging.error(f"Failed to save used manifest ID: {e}")

def pick_new_manifest():
    all_m = load_manifestations()
    used = get_used_ids()
    available = [m for m in all_m if m["id"] not in used]
    if not available:
        logging.warning("No new manifestations left. Reusing from old.")
        return random.choice(all_m) if all_m else None
    chosen = random.choice(available)
    save_used_id(chosen["id"])
    logging.info(f"Picked new manifestation ID: {chosen['id']}")
    return chosen

async def send_manifestation(app, index):
    try:
        manifest = app.bot_data.get("today_manifest")
        if not manifest:
            manifest = pick_new_manifest()
            app.bot_data["today_manifest"] = manifest

        if manifest:
            text = manifest['set'][index]
            await app.bot.send_message(CHAT_ID, text=f"🌅 Manifestation:\n\n{text}")
            logging.info(f"Sent manifestation {index + 1}/3: {text[:40]}...")
        else:
            logging.error("No valid manifestation to send.")
    except Exception as e:
        logging.error(f"Error sending manifestation {index + 1}: {e}")
