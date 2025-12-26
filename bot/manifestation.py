# bot/manifestation.py
"""
Robust manifestation rotation with deterministic fallback.

Behavior:
- Prefer persisted rotation: uses V30X_DATA_DIR (or ~/.vison30x).
- Persist today's chosen id in today_manifestation.json and used ids in used_manifestations.json.
- If persistence fails or runtime dir is not writable, fallback to a deterministic choice:
    index = sha256(f"{date_iso}_{CHAT_ID}") % N
  which changes per calendar day and CHAT_ID, ensuring no daily repeats.

Keeps API:
- async def send_manifestation(app, index: int)
"""

from __future__ import annotations

import os
import json
import random
import logging
import threading
import hashlib
from datetime import datetime, date
from pathlib import Path
from typing import Optional

from bot.reflection import record_reflection

# ----------------------------
# Paths & config
# ----------------------------
BASE_DIR = Path(__file__).resolve().parent
READONLY_DATA_DIR = BASE_DIR / "data"  # manifestations.json (repo)
RUNTIME_DIR = Path(os.getenv("V30X_DATA_DIR", Path.home() / ".vison30x"))
RUNTIME_DIR.mkdir(parents=True, exist_ok=True)

MANIFESTATIONS_FILE = READONLY_DATA_DIR / "manifestations.json"
USED_FILE = RUNTIME_DIR / "used_manifestations.json"
TODAY_FILE = RUNTIME_DIR / "today_manifestation.json"

TZ_NAME = os.getenv("V30X_TZ", "Asia/Kolkata")

_lock = threading.Lock()
_cached_date: Optional[date] = None
_cached_manifestation: Optional[dict] = None

# ----------------------------
# Utilities
# ----------------------------
def _today_local_date() -> date:
    try:
        from zoneinfo import ZoneInfo
        return datetime.now(ZoneInfo(TZ_NAME)).date()
    except Exception:
        return datetime.now().date()

def _atomic_write(path: Path, obj) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
    tmp.replace(path)

# ----------------------------
# Load manifest list
# ----------------------------
def load_manifestations() -> list:
    try:
        with MANIFESTATIONS_FILE.open("r", encoding="utf-8") as f:
            data = json.load(f)
            if not isinstance(data, list):
                logging.error("[Manifestation] manifestations.json malformed (not list).")
                return []
            return data
    except Exception as e:
        logging.exception("[Manifestation] Failed to load manifestations.json: %s", e)
        return []

# ----------------------------
# Persistence helpers
# ----------------------------
def load_used_ids() -> set[int]:
    if not USED_FILE.exists():
        return set()
    try:
        with USED_FILE.open("r", encoding="utf-8") as f:
            raw = json.load(f)
            return set(int(x) for x in raw)
    except Exception as e:
        logging.warning("[Manifestation] Failed to load used ids (%s): %s", USED_FILE, e)
        return set()

def save_used_ids_safe(used_ids: set[int]) -> bool:
    try:
        _atomic_write(USED_FILE, sorted(list(used_ids)))
        return True
    except Exception:
        return False

def load_today_state() -> Optional[dict]:
    if not TODAY_FILE.exists():
        return None
    try:
        with TODAY_FILE.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None

def save_today_state_safe(state: dict) -> bool:
    try:
        _atomic_write(TODAY_FILE, state)
        return True
    except Exception:
        return False

# ----------------------------
# Deterministic fallback selection
# ----------------------------
def deterministic_choice_by_date(manifestations: list, salt: str = "") -> dict:
    today = _today_local_date().isoformat()
    key = f"{today}|{salt}"
    h = hashlib.sha256(key.encode("utf-8")).digest()
    idx = int.from_bytes(h[:8], "big") % len(manifestations)
    return manifestations[idx]

# ----------------------------
# Normal pick with persistence
# ----------------------------
def pick_new_manifestation(manifestations: list, used_ids: set[int]) -> dict:
    unused = [m for m in manifestations if int(m.get("id")) not in used_ids]
    if not unused:
        used_ids.clear()
        unused = manifestations
    chosen = random.choice(unused)
    used_ids.add(int(chosen.get("id")))
    save_used_ids_safe(used_ids)
    return chosen

# ----------------------------
# Public function: get today's manifestation
# ----------------------------
def get_today_manifestation() -> Optional[dict]:
    global _cached_date, _cached_manifestation
    with _lock:
        today = _today_local_date()
        if _cached_date == today and _cached_manifestation is not None:
            return _cached_manifestation

        mans = load_manifestations()
        if not mans:
            return None

        state = load_today_state()
        if state and state.get("date") == today.isoformat():
            chosen = next((m for m in mans if int(m.get("id")) == int(state.get("id"))), None)
            if chosen:
                _cached_date = today
                _cached_manifestation = chosen
                return chosen

        try:
            used_ids = load_used_ids()
            chosen = pick_new_manifestation(mans, used_ids)
            save_today_state_safe({"date": today.isoformat(), "id": int(chosen.get("id"))})
        except Exception:
            chosen = deterministic_choice_by_date(mans, salt=os.getenv("CHAT_ID", ""))

        _cached_date = today
        _cached_manifestation = chosen
        return chosen

# ----------------------------
# Bot send function
# ----------------------------
async def send_manifestation(app, index: int):
    manifestation = get_today_manifestation()
    if not manifestation:
        return

    the_set = manifestation.get("set", [])
    if index < 0 or index >= len(the_set):
        return

    line = the_set[index]
    chat_id = int(os.getenv("CHAT_ID"))

    await app.bot.send_message(
        chat_id=chat_id,
        text=f"🌅 Manifestation:\n\n{line}"
    )

    # 🔒 Reflection Artifact (append-only)
    record_reflection(
        reflection_type="manifestation",
        payload_id=str(manifestation.get("id")),
        recipient="me",
    )
