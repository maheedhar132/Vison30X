import os
import json
import random
import logging
from datetime import datetime
from pathlib import Path

from telegram import Bot

# Constants
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
MANIFESTATIONS_FILE = DATA_DIR / "manifestations.json"
USED_FILE = DATA_DIR / "used_manifestations.json"

# Ensure directory exists
DATA_DIR.mkdir(parents=True, exist_ok=True)

# Load manifestation data
def load_manifestations():
    try:
        with open(MANIFESTATIONS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logging.error(f"[Manifestation] Failed to load manifestations: {e}")
        return []

def load_used_ids():
    if not USED_FILE.exists():
        return set()
    try:
        with open(USED_FILE, "r", encoding="utf-8") as f:
            return set(json.load(f))
    except Exception as e:
        logging.warning(f"[Manifestation] Failed to load used_manifestations: {e}")
        return set()

def save_used_ids(used_ids):
    try:
        with open(USED_FILE, "w", encoding="utf-8") as f:
            json.dump(sorted(list(used_ids)), f, indent=2)
    except Exception as e:
        logging.error(f"[Manifestation] Failed to save used_manifestations: {e}")

# Pick a new manifestation
def pick_new_manifestation(manifestations, used_ids):
    unused = [m for m in manifestations if m["id"] not in used_ids]
    if not unused:
        logging.warning("[Manifestation] All manifestations used. Resetting the list.")
        used_ids.clear()
        unused = manifestations

    chosen = random.choice(unused)
    used_ids.add(chosen["id"])
    save_used_ids(used_ids)
    return chosen

# Global cache to avoid repeated picks per day
_cached_today = None
_cached_manifestation = None

def get_today_manifestation():
    global _cached_today, _cached_manifestation
    today = datetime.now().date()

    if _cached_today != today:
        manifestations = load_manifestations()
        used_ids = load_used_ids()
        _cached_manifestation = pick_new_manifestation(manifestations, used_ids)
        _cached_today = today

    return _cached_manifestation

# Bot entrypoint (used in scheduler)
async def send_manifestation(app, index):
    try:
        manifestation = get_today_manifestation()
        line = manifestation["set"][index]
        message = f"🌅 Manifestation:\n\n{line}"
        await app.bot.send_message(chat_id=int(os.getenv("CHAT_ID")), text=message)
        logging.info(f"[Manifestation] Sent index {index} from ID {manifestation['id']}")
    except Exception as e:
        logging.exception(f"[Manifestation] Failed to send manifestation: {e}")
        await app.bot.send_message(chat_id=int(os.getenv("CHAT_ID")), text="❌ Failed to send manifestation.")
