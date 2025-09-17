# bot/cards.py
"""
Card draw + reveal module.
Behavior:
- On draw: choose (or reuse persisted) a card for today and send the hidden prompt to both CHAT_ID and CHAT_ID_HER.
- On reveal: reveal the same card to both CHAT_ID and CHAT_ID_HER.
- Persists today_card.json in V30X_DATA_DIR (or ~/.vison30x) so restarts don't redraw different cards mid-day.
"""

from __future__ import annotations

import os
import json
import logging
import random
from datetime import datetime, date
from pathlib import Path
from typing import Optional

# runtime / repo paths
BASE_DIR = Path(__file__).resolve().parent
READONLY_DATA_DIR = BASE_DIR / "data"   # should contain cards.json (repo)
RUNTIME_DIR = Path(os.getenv("V30X_DATA_DIR", Path.home() / ".vison30x"))
RUNTIME_DIR.mkdir(parents=True, exist_ok=True)

CARDS_FILE = READONLY_DATA_DIR / "cards.json"
TODAY_CARD_FILE = RUNTIME_DIR / "today_card.json"

# helper: atomic write
def _atomic_write(path: Path, obj) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
    tmp.replace(path)

# load cards list
def load_cards() -> list:
    try:
        with CARDS_FILE.open("r", encoding="utf-8") as f:
            data = json.load(f)
            if not isinstance(data, list):
                logging.error("[Cards] cards.json malformed (expected list).")
                return []
            return data
    except Exception as e:
        logging.exception("[Cards] Failed to load cards.json: %s", e)
        return []

def load_today_card_state() -> Optional[dict]:
    """Return {'date': 'YYYY-MM-DD', 'id': <card_id>} or None."""
    if not TODAY_CARD_FILE.exists():
        return None
    try:
        with TODAY_CARD_FILE.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logging.warning("[Cards] Failed to load today card state: %s", e)
        return None

def save_today_card_state(state: dict) -> bool:
    try:
        _atomic_write(TODAY_CARD_FILE, state)
        logging.info("[Cards] Saved today_card state: %s", state)
        return True
    except Exception as e:
        logging.exception("[Cards] Failed to save today_card state: %s", e)
        return False

def pick_random_card(cards: list) -> Optional[dict]:
    if not cards:
        return None
    return random.choice(cards)

def _today_local_date_iso() -> str:
    try:
        from zoneinfo import ZoneInfo
        tz = os.getenv("V30X_TZ", "Asia/Kolkata")
        return datetime.now(ZoneInfo(tz)).date().isoformat()
    except Exception:
        return datetime.now().date().isoformat()

# Public API used by scheduler/handlers --------------------------------------

async def send_card_prompt(app):
    """
    Draw (or reuse) today's card and send the *hidden* prompt/message to both users (you + her).
    Keeps compatibility with existing scheduler which calls send_card_prompt(context.application).
    """
    try:
        cards = load_cards()
        if not cards:
            logging.error("[Cards] No cards available to draw.")
            return

        today = _today_local_date_iso()
        state = load_today_card_state()
        chosen_card = None

        # Reuse persisted today's card if date matches
        if state and state.get("date") == today:
            card_id = state.get("id")
            chosen_card = next((c for c in cards if c.get("title") == card_id or c.get("id") == card_id), None)
            if chosen_card:
                logging.info("[Cards] Reusing persisted today card: %s", card_id)

        # If no persisted or not found, pick a random one and persist
        if not chosen_card:
            chosen_card = pick_random_card(cards)
            if not chosen_card:
                logging.error("[Cards] Failed to pick a card.")
                return
            # We persist by using either "id" field if present else "title" as identifier
            card_identifier = chosen_card.get("id") if chosen_card.get("id") is not None else chosen_card.get("title")
            save_today_card_state({"date": today, "id": card_identifier})
            logging.info("[Cards] Drew and persisted today card: %s", card_identifier)

        # prepare the hidden prompt message
        hidden_msg = chosen_card.get("message", "")
        title = chosen_card.get("title", "Today’s Card")
        prompt_text = chosen_card.get("prompt", "")

        # A subtle hidden prompt: we send the message but keep "reveal" semantics for later
        # You can customise formatting here if you want the prompt to remain hidden (e.g., replaced text)
        hidden_payload = f"🃏 Card drawn — keep this safe until reveal.\n\n*{title}*\n\n{hidden_msg}\n\n(Will be revealed later.)"

        # send to both chats (if configured)
        chat_me = os.getenv("CHAT_ID")
        chat_her = os.getenv("CHAT_ID_HER")

        if chat_me:
            try:
                await app.bot.send_message(chat_id=int(chat_me), text=hidden_payload, parse_mode="Markdown")
            except Exception as e:
                logging.exception("[Cards] Failed to send hidden card to CHAT_ID: %s", e)

        if chat_her:
            try:
                await app.bot.send_message(chat_id=int(chat_her), text=hidden_payload, parse_mode="Markdown")
            except Exception as e:
                logging.exception("[Cards] Failed to send hidden card to CHAT_ID_HER: %s", e)

        logging.info("[Cards] Hidden prompt sent to both recipients (if available).")
    except Exception as e:
        logging.exception("[Cards] send_card_prompt error: %s", e)


async def send_card_reveal(app):
    """
    Reveal today's card (same card drawn earlier) to both users with the full prompt + reflective question.
    """
    try:
        cards = load_cards()
        if not cards:
            logging.error("[Cards] No cards available to reveal.")
            return

        today = _today_local_date_iso()
        state = load_today_card_state()
        chosen_card = None

        # If persisted card exists for today, find it
        if state and state.get("date") == today:
            card_id = state.get("id")
            chosen_card = next((c for c in cards if c.get("title") == card_id or c.get("id") == card_id), None)

        # If not persisted or not found, pick deterministic/random fallback (so reveal still happens)
        if not chosen_card:
            chosen_card = pick_random_card(cards)
            logging.warning("[Cards] No persisted today card found at reveal time — picking random for reveal.")

        title = chosen_card.get("title", "Today's Card")
        message = chosen_card.get("message", "")
        prompt = chosen_card.get("prompt", "")

        reveal_payload = f"🔔 Card Reveal\n\n*{title}*\n\n{message}\n\n*Reflection:* {prompt}"

        chat_me = os.getenv("CHAT_ID")
        chat_her = os.getenv("CHAT_ID_HER")

        if chat_me:
            try:
                await app.bot.send_message(chat_id=int(chat_me), text=reveal_payload, parse_mode="Markdown")
            except Exception as e:
                logging.exception("[Cards] Failed to send reveal to CHAT_ID: %s", e)

        if chat_her:
            try:
                await app.bot.send_message(chat_id=int(chat_her), text=reveal_payload, parse_mode="Markdown")
            except Exception as e:
                logging.exception("[Cards] Failed to send reveal to CHAT_ID_HER: %s", e)

        logging.info("[Cards] Card revealed to both recipients (if available).")
    except Exception as e:
        logging.exception("[Cards] send_card_reveal error: %s", e)


# optional helper to clear today's persisted card (useful for reset/testing)
def clear_today_card_state():
    try:
        if TODAY_CARD_FILE.exists():
            TODAY_CARD_FILE.unlink()
            logging.info("[Cards] Cleared today_card.json")
    except Exception as e:
        logging.exception("[Cards] Failed to clear today card state: %s", e)
