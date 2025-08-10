import os
import json
import random
import logging
from datetime import datetime
from pathlib import Path
from telegram import Bot

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
MANIFESTATIONS_FILE = DATA_DIR / "manifestations_for_her.json"
USED_FILE = DATA_DIR / "used_manifestations_for_her.json"

DATA_DIR.mkdir(parents=True, exist_ok=True)

def load_manifestations():
    try:
        with open(MANIFESTATIONS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logging.error(f"[ManifestationHer] Failed to load: {e}")
        return []

def load_used_ids():
    if not USED_FILE.exists():
        return set()
    try:
        with open(USED_FILE, "r", encoding="utf-8") as f:
            return set(json.load(f))
    except:
        return set()

def save_used_ids(used_ids):
    try:
        with open(USED_FILE, "w", encoding="utf-8") as f:
            json.dump(sorted(list(used_ids)), f, indent=2)
    except Exception as e:
        logging.error(f"[ManifestationHer] Save error: {e}")

def pick_new_manifestation(manifestations, used_ids):
    unused = [m for m in manifestations if m["id"] not in used_ids]
    if not unused:
        used_ids.clear()
        unused = manifestations
    chosen = random.choice(unused)
    used_ids.add(chosen["id"])
    save_used_ids(used_ids)
    return chosen

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

async def send_manifestation_for_her(app, index):
    try:
        manifestation = get_today_manifestation()
        line = manifestation["set"][index]
        message = f"🌅 Manifestation for Her:\n\n{line}"
        await app.bot.send_message(chat_id=int(os.getenv("CHAT_ID_HER")), text=message)
        logging.info(f"[ManifestationHer] Sent index {index} from ID {manifestation['id']}")
    except Exception as e:
        logging.exception(f"[ManifestationHer] Failed to send: {e}")
