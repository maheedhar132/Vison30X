# bot/cards.py
"""
Card draw + reveal module (robust).
- send_card_prompt(app): draw/reuse today's card and ANNOUNCE the draw only.
- send_card_reveal(app): reveal the SAME persisted card in a boxed monospace layout to both CHAT_ID and CHAT_ID_HER.
Persistence: TODAY_CARD_FILE stored in V30X_DATA_DIR (or ~/.vison30x).
"""

from __future__ import annotations

import os
import json
import logging
import random
import textwrap
from datetime import datetime
from pathlib import Path
from html import escape
from typing import Optional

# Optional: load .env fallback with python-dotenv
try:
    from dotenv import load_dotenv  # type: ignore
except Exception:
    load_dotenv = None  # type: ignore

# ----------------------------
# Paths & files
# ----------------------------
BASE_DIR = Path(__file__).resolve().parent
READONLY_DATA_DIR = BASE_DIR / "data"  # repo cards.json expected here
RUNTIME_DIR = Path(os.getenv("V30X_DATA_DIR", Path.home() / ".vison30x"))
RUNTIME_DIR.mkdir(parents=True, exist_ok=True)

CARDS_FILE = READONLY_DATA_DIR / "cards.json"
TODAY_CARD_FILE = RUNTIME_DIR / "today_card.json"

# ----------------------------
# Helpers: tz-aware today iso
# ----------------------------
TZ_NAME = os.getenv("V30X_TZ", "Asia/Kolkata")


def _today_local_date_iso() -> str:
    try:
        from zoneinfo import ZoneInfo  # Python 3.9+
        return datetime.now(ZoneInfo(TZ_NAME)).date().isoformat()
    except Exception:
        return datetime.now().date().isoformat()


# ----------------------------
# Atomic write helper
# ----------------------------
def _atomic_write(path: Path, obj) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
    tmp.replace(path)


# ----------------------------
# Load cards (repo)
# ----------------------------
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


# ----------------------------
# Persisted state helpers
# ----------------------------
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


# ----------------------------
# Card selection
# ----------------------------
def pick_random_card(cards: list) -> Optional[dict]:
    if not cards:
        return None
    return random.choice(cards)


# ----------------------------
# Robust env access (fallback to project .env)
# ----------------------------
def _get_env_var(name: str) -> Optional[str]:
    # 1) try process environment
    v = os.getenv(name)
    if v:
        return v.strip()

    # 2) fallback: try loading .env from project root if python-dotenv is available
    try:
        project_root = Path(__file__).resolve().parents[1]
        dotenv_path = project_root / ".env"
        if dotenv_path.exists() and load_dotenv:
            load_dotenv(dotenv_path)
            v2 = os.getenv(name)
            if v2:
                return v2.strip()
    except Exception as e:
        logging.debug("[Cards] .env fallback failed to load %s: %s", name, e)
    return None


def _norm_chat_id(v: Optional[str]) -> Optional[int]:
    if not v:
        return None
    try:
        vstr = str(v).strip()
        # remove surrounding quotes if accidentally present
        if (vstr.startswith('"') and vstr.endswith('"')) or (vstr.startswith("'") and vstr.endswith("'")):
            vstr = vstr[1:-1].strip()
        return int(vstr)
    except Exception as e:
        logging.exception("[Cards] CHAT_ID parse error for value %r: %s", v, e)
        return None


# ----------------------------
# Boxed card renderer (monospace)
# ----------------------------
def _render_boxed_card(title: str, message: str, prompt: str, inner_width: int = 56) -> str:
    """
    Render a boxed card using unicode box chars and return string to be placed inside <pre>.
    inner_width: number of characters inside the content area (approx).
    """
    # Clean inputs
    title = title.strip()
    message = message.strip()
    prompt = prompt.strip()

    # box pieces
    tl = "┌"
    tr = "┐"
    bl = "└"
    br = "┘"
    h = "─"
    v = "│"
    sep_l = "├"
    sep_r = "┤"

    # Wrapping helpers
    wrapper = textwrap.TextWrapper(width=max(10, inner_width - 2), replace_whitespace=True)

    # Prepare sections
    title_line = title.center(inner_width)
    message_lines = wrapper.wrap(message) or [""]
    prompt_lines = wrapper.wrap(prompt) or [""]

    # Build box
    lines = []
    lines.append(tl + h * (inner_width + 1) + tr)
    lines.append(f"{v} {title_line.ljust(inner_width - 1)}{v}")
    lines.append(sep_l + h * (inner_width + 1) + sep_r)
    # small spacer/visual area (keeps room for an icon if you later want one)
    lines.append(f"{v} {'':{inner_width - 1}}{v}")
    # message block
    for ml in message_lines:
        lines.append(f"{v} {' ' + ml.ljust(inner_width - 2) if ml else ''.ljust(inner_width - 1)}{v}")
    lines.append(sep_l + h * (inner_width + 1) + sep_r)
    # prompt block
    for pl in prompt_lines:
        lines.append(f"{v} {' ' + pl.ljust(inner_width - 2) if pl else ''.ljust(inner_width - 1)}{v}")
    lines.append(bl + h * (inner_width + 1) + br)

    return "\n".join(lines)


# ----------------------------
# Public API: announce draw (no reveal content)
# ----------------------------
async def send_card_prompt(app):
    """
    Draw (or reuse) today's card and ANNOUNCE the draw only to both recipients.
    The actual card content is not shown here; it's kept for the reveal.
    """
    try:
        cards = load_cards()
        if not cards:
            logging.error("[Cards] No cards available to draw.")
            return

        today = _today_local_date_iso()
        state = load_today_card_state()
        chosen_card = None

        # reuse if persisted
        if state and state.get("date") == today:
            card_id = state.get("id")
            chosen_card = next((c for c in cards if c.get("title") == card_id or c.get("id") == card_id), None)
            if chosen_card:
                logging.info("[Cards] Reusing persisted today card: %s", card_id)

        # pick and persist if not found
        if not chosen_card:
            chosen_card = pick_random_card(cards)
            if not chosen_card:
                logging.error("[Cards] Failed to pick a card.")
                return
            card_identifier = chosen_card.get("id") if chosen_card.get("id") is not None else chosen_card.get("title")
            save_today_card_state({"date": today, "id": card_identifier})
            logging.info("[Cards] Drew and persisted today card: %s", card_identifier)

        # Announce draw only (no content)
        announce_text = (
            "🃏 Card drawn — take a quiet moment to reflect on your day.\n\n"
            "When it's time, you'll receive the full card reveal."
        )

        # Resolve chat ids robustly
        chat_me = _get_env_var("CHAT_ID")
        chat_her = _get_env_var("CHAT_ID_HER")
        chat_me_id = _norm_chat_id(chat_me)
        chat_her_id = _norm_chat_id(chat_her)

        if not chat_me_id and not chat_her_id:
            logging.error("[Cards] Neither CHAT_ID nor CHAT_ID_HER available to send announcement.")
            return

        if chat_me_id:
            try:
                await app.bot.send_message(chat_id=chat_me_id, text=announce_text)
                logging.info("[Cards] Announced draw to CHAT_ID (%s).", chat_me_id)
            except Exception as e:
                logging.exception("[Cards] Failed to announce draw to CHAT_ID (%s): %s", chat_me_id, e)

        if chat_her_id:
            try:
                await app.bot.send_message(chat_id=chat_her_id, text=announce_text)
                logging.info("[Cards] Announced draw to CHAT_ID_HER (%s).", chat_her_id)
            except Exception as e:
                logging.exception("[Cards] Failed to announce draw to CHAT_ID_HER (%s): %s", chat_her_id, e)

    except Exception as e:
        logging.exception("[Cards] send_card_prompt error: %s", e)


# ----------------------------
# Public API: reveal boxed card (monospace)
# ----------------------------
async def send_card_reveal(app):
    """
    Reveal today's card to both recipients in a boxed monospace layout,
    using an HTML <pre> block so formatting is preserved in Telegram.
    """
    try:
        cards = load_cards()
        if not cards:
            logging.error("[Cards] No cards available to reveal.")
            return

        today = _today_local_date_iso()
        state = load_today_card_state()
        chosen_card = None

        if state and state.get("date") == today:
            card_id = state.get("id")
            chosen_card = next((c for c in cards if c.get("title") == card_id or c.get("id") == card_id), None)

        if not chosen_card:
            chosen_card = pick_random_card(cards)
            logging.warning("[Cards] No persisted today card found at reveal time — picking random for reveal.")

        title = chosen_card.get("title", "Your Card")
        message = chosen_card.get("message", "")
        prompt = chosen_card.get("prompt", "")

        # Render boxed card
        boxed = _render_boxed_card(title=title, message=message, prompt=prompt, inner_width=56)

        # Escape and send inside HTML <pre>
        payload = f"<pre>{escape(boxed)}</pre>"

        chat_me = _get_env_var("CHAT_ID")
        chat_her = _get_env_var("CHAT_ID_HER")
        chat_me_id = _norm_chat_id(chat_me)
        chat_her_id = _norm_chat_id(chat_her)

        if not chat_me_id and not chat_her_id:
            logging.error("[Cards] Neither CHAT_ID nor CHAT_ID_HER available to send reveal.")
            return

        if chat_me_id:
            try:
                await app.bot.send_message(chat_id=chat_me_id, text=payload, parse_mode="HTML")
                logging.info("[Cards] Revealed boxed card to CHAT_ID (%s).", chat_me_id)
            except Exception as e:
                logging.exception("[Cards] Failed to reveal boxed card to CHAT_ID (%s): %s", chat_me_id, e)

        if chat_her_id:
            try:
                await app.bot.send_message(chat_id=chat_her_id, text=payload, parse_mode="HTML")
                logging.info("[Cards] Revealed boxed card to CHAT_ID_HER (%s).", chat_her_id)
            except Exception as e:
                logging.exception("[Cards] Failed to reveal boxed card to CHAT_ID_HER (%s): %s", chat_her_id, e)

    except Exception as e:
        logging.exception("[Cards] send_card_reveal error: %s", e)


# ----------------------------
# Optional helper: clear today's card (for testing)
# ----------------------------
def clear_today_card_state() -> None:
    try:
        if TODAY_CARD_FILE.exists():
            TODAY_CARD_FILE.unlink()
            logging.info("[Cards] Cleared today_card.json")
    except Exception as e:
        logging.exception("[Cards] Failed to clear today card state: %s", e)
