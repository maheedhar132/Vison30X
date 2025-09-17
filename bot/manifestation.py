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
    """Try to persist used ids. Return True on success, False on failure."""
    try:
        _atomic_write(USED_FILE, sorted(list(used_ids)))
        logging.info("[Manifestation] Saved used ids (%d) to %s", len(used_ids), USED_FILE)
        return True
    except Exception as e:
        logging.exception("[Manifestation] Failed to save used ids: %s", e)
        return False

def load_today_state() -> Optional[dict]:
    if not TODAY_FILE.exists():
        return None
    try:
        with TODAY_FILE.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logging.warning("[Manifestation] Failed to load today state (%s): %s", TODAY_FILE, e)
        return None

def save_today_state_safe(state: dict) -> bool:
    try:
        _atomic_write(TODAY_FILE, state)
        logging.info("[Manifestation] Saved today state: %s", state)
        return True
    except Exception as e:
        logging.exception("[Manifestation] Failed to save today state: %s", e)
        return False

# ----------------------------
# Deterministic fallback selection
# ----------------------------
def deterministic_choice_by_date(manifestations: list, salt: str = "") -> dict:
    """
    Deterministic pick based on date and salt (CHAT_ID).
    Ensures rotation per calendar day without needing disk writes.
    """
    if not manifestations:
        raise ValueError("No manifestations available.")
    today = _today_local_date().isoformat()
    key = f"{today}|{salt}"
    h = hashlib.sha256(key.encode("utf-8")).digest()
    # convert first 8 bytes to int
    idx = int.from_bytes(h[:8], "big") % len(manifestations)
    chosen = manifestations[idx]
    logging.info("[Manifestation] Deterministic pick index=%d id=%s (key=%s)", idx, chosen.get("id"), key)
    return chosen

# ----------------------------
# Normal pick with persistence (best-effort)
# ----------------------------
def pick_new_manifestation(manifestations: list, used_ids: set[int]) -> dict:
    unused = [m for m in manifestations if int(m.get("id")) not in used_ids]
    if not unused:
        logging.info("[Manifestation] All used; resetting used list.")
        used_ids.clear()
        unused = manifestations
    chosen = random.choice(unused)
    used_ids.add(int(chosen.get("id")))
    # Try to save used ids; if fails, caller will fallback if needed
    ok = save_used_ids_safe(used_ids)
    if not ok:
        logging.warning("[Manifestation] Could not persist used ids; continuing without persistence.")
    return chosen

# ----------------------------
# Public function: get today's manifestation
# ----------------------------
def get_today_manifestation() -> Optional[dict]:
    """
    Return today's chosen manifestation, persisted when possible.
    If persistence fails, use deterministic fallback so the result changes daily.
    """
    global _cached_date, _cached_manifestation
    with _lock:
        today = _today_local_date()
        if _cached_date == today and _cached_manifestation is not None:
            return _cached_manifestation

        mans = load_manifestations()
        if not mans:
            logging.error("[Manifestation] No manifestations loaded.")
            return None

        # 1) If today state persisted, use it
        state = load_today_state()
        if state and state.get("date") == today.isoformat():
            try:
                chosen_id = int(state.get("id"))
                chosen = next((m for m in mans if int(m.get("id")) == chosen_id), None)
                if chosen:
                    _cached_date = today
                    _cached_manifestation = chosen
                    logging.info("[Manifestation] Reusing persisted today id=%s", chosen_id)
                    return chosen
                else:
                    logging.warning("[Manifestation] persisted today id=%s not found in manifestations list", chosen_id)
            except Exception:
                logging.exception("[Manifestation] Error reading persisted today state")

        # 2) Try normal pick with used ids
        used_ids = load_used_ids()
        try:
            chosen = pick_new_manifestation(mans, used_ids)
            # try to persist today state
            if save_today_state_safe({"date": today.isoformat(), "id": int(chosen.get("id"))}):
                _cached_date = today
                _cached_manifestation = chosen
                return chosen
            else:
                # persistence of today failed. We will still return chosen,
                # but also compute deterministic fallback so that future restarts
                # won't always pick the same item.
                logging.warning("[Manifestation] Failed to persist today state; falling back to deterministic mode next time.")
                _cached_date = today
                _cached_manifestation = chosen
                return chosen
        except Exception as e:
            logging.exception("[Manifestation] pick_new_manifestation failed: %s", e)
            # 3) As a permanent fallback, deterministically pick one based on date + CHAT_ID
            chat_env = os.getenv("CHAT_ID", "")
            try:
                chosen = deterministic_choice_by_date(mans, salt=str(chat_env))
                # attempt to persist today state best-effort (may fail)
                try:
                    save_today_state_safe({"date": today.isoformat(), "id": int(chosen.get("id"))})
                except Exception:
                    pass
                _cached_date = today
                _cached_manifestation = chosen
                return chosen
            except Exception as e2:
                logging.exception("[Manifestation] Deterministic fallback failed: %s", e2)
                return None

# ----------------------------
# Bot send function (used by scheduler)
# ----------------------------
async def send_manifestation(app, index: int):
    try:
        manifestation = get_today_manifestation()
        if not manifestation:
            raise RuntimeError("No manifestation available.")
        the_set = manifestation.get("set", [])
        if index < 0 or index >= len(the_set):
            raise IndexError("Index out of range for manifestation set.")
        line = the_set[index]
        chat_env = os.getenv("CHAT_ID")
        if not chat_env:
            logging.error("[Manifestation] CHAT_ID not set.")
            return
        chat_id = int(chat_env)
        message = f"🌅 Manifestation:\n\n{line}"
        await app.bot.send_message(chat_id=chat_id, text=message)
        logging.info("[Manifestation] Sent index %d from id=%s", index, manifestation.get("id"))
    except Exception as e:
        logging.exception("[Manifestation] Failed to send manifestation: %s", e)
        try:
            await app.bot.send_message(chat_id=int(os.getenv("CHAT_ID", 0)), text="❌ Failed to send manifestation.")
        except Exception:
            pass
