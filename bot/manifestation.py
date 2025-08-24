import os
import json
import random
import logging
import threading
from datetime import datetime, date
from pathlib import Path

# ----------------------------
# Paths
# ----------------------------
BASE_DIR = Path(__file__).resolve().parent
READONLY_DATA_DIR = BASE_DIR / "data"  # manifestations.json lives here

# Writable runtime dir: env override or ~/.vison30x
RUNTIME_DIR = Path(os.getenv("V30X_DATA_DIR", Path.home() / ".vison30x"))
RUNTIME_DIR.mkdir(parents=True, exist_ok=True)

MANIFESTATIONS_FILE = READONLY_DATA_DIR / "manifestations.json"
USED_FILE = RUNTIME_DIR / "used_manifestations.json"
TODAY_FILE = RUNTIME_DIR / "today_manifestation.json"

# Optional: timezone awareness for "today"
TZ_NAME = os.getenv("V30X_TZ", "Asia/Kolkata")

_lock = threading.Lock()
_cached_date: date | None = None
_cached_manifestation: dict | None = None

def _today_local() -> date:
    # Keep it simple: if Python 3.9+, use zoneinfo; else fall back to naive local
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

def load_manifestations() -> list:
    try:
        with MANIFESTATIONS_FILE.open("r", encoding="utf-8") as f:
            data = json.load(f)
            # validate shape: list of {id,set:[...]}
            if not isinstance(data, list):
                raise ValueError("manifestations.json is not a list")
            return data
    except Exception as e:
        logging.error(f"[Manifestation] Failed to load manifestations: {e}")
        return []

def load_used_ids() -> set[int]:
    if not USED_FILE.exists():
        return set()
    try:
        with USED_FILE.open("r", encoding="utf-8") as f:
            raw = json.load(f)
            return set(int(x) for x in raw)
    except Exception as e:
        logging.warning(f"[Manifestation] Failed to load used ids: {e}")
        return set()

def save_used_ids(used_ids: set[int]) -> None:
    try:
        _atomic_write(USED_FILE, sorted(list(used_ids)))
    except Exception as e:
        logging.error(f"[Manifestation] Failed to save used ids: {e}")

def load_today_state():
    """Return dict like {'date': '2025-08-24', 'id': 42} or None."""
    if not TODAY_FILE.exists():
        return None
    try:
        with TODAY_FILE.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logging.warning(f"[Manifestation] Failed to load today state: {e}")
        return None

def save_today_state(d: dict) -> None:
    try:
        _atomic_write(TODAY_FILE, d)
    except Exception as e:
        logging.error(f"[Manifestation] Failed to save today state: {e}")

def pick_new_manifestation(manifestations: list, used_ids: set[int]) -> dict:
    unused = [m for m in manifestations if int(m.get("id")) not in used_ids]
    if not unused:
        # Reset cycle
        logging.info("[Manifestation] All manifestations used. Resetting list.")
        used_ids.clear()
        unused = manifestations

    chosen = random.choice(unused)
    used_ids.add(int(chosen["id"]))
    save_used_ids(used_ids)
    return chosen

def get_today_manifestation() -> dict | None:
    """
    Deterministically return today's manifestation:
    - If today's pick is persisted, reuse it.
    - Else pick a new unused one, persist it (with date), and return it.
    Caches in-process per calendar day (Asia/Kolkata by default).
    """
    global _cached_date, _cached_manifestation
    with _lock:
        today = _today_local()

        # in-process cache
        if _cached_date == today and _cached_manifestation is not None:
            return _cached_manifestation

        # persisted state
        state = load_today_state()
        if state and state.get("date") == today.isoformat():
            # Load the chosen id from today-file
            man_list = load_manifestations()
            chosen = next((m for m in man_list if int(m.get("id")) == int(state.get("id"))), None)
            if chosen:
                _cached_date = today
                _cached_manifestation = chosen
                return chosen
            # if not found (manifest file changed), fall through to re-pick

        # pick new & persist
        man_list = load_manifestations()
        if not man_list:
            return None
        used = load_used_ids()
        chosen = pick_new_manifestation(man_list, used)
        save_today_state({"date": today.isoformat(), "id": int(chosen["id"])})
        _cached_date = today
        _cached_manifestation = chosen
        return chosen

# Bot entrypoint (used in scheduler)
async def send_manifestation(app, index: int):
    try:
        manifestation = get_today_manifestation()
        if not manifestation:
            raise RuntimeError("No manifestations available.")
        # Guard against bad index
        the_set = manifestation.get("set", [])
        if index < 0 or index >= len(the_set):
            raise IndexError(f"Index {index} out of range for set of length {len(the_set)} (id={manifestation.get('id')})")

        line = the_set[index]
        message = f"🌅 Manifestation:\n\n{line}"
        chat_id = int(os.getenv("CHAT_ID"))
        await app.bot.send_message(chat_id=chat_id, text=message)
        logging.info(f"[Manifestation] Sent index {index} from ID {manifestation['id']}")
    except Exception as e:
        logging.exception(f"[Manifestation] Failed to send manifestation: {e}")
        try:
            await app.bot.send_message(chat_id=int(os.getenv("CHAT_ID")), text="❌ Failed to send manifestation.")
        except Exception:
            pass
