# bot/handlers.py

from __future__ import annotations

import logging
import os
import traceback
from datetime import datetime
import pytz

from telegram import Update
from telegram.ext import CommandHandler, ContextTypes, Application

from telegram.ext import CommandHandler, CallbackQueryHandler
from bot.focus import start_pomodoro, handle_phone_free_callback
from bot.db import get_focus_status, set_focus_target

# Your project modules
from bot import manifestation as manifestation_module
from bot import cards as cards_module
from bot.manifestation import send_manifestation
from bot.manifestation_for_her import send_manifestation_for_her
from bot.cards import send_card_prompt, send_card_reveal
# Testing helpers from the new scheduler implementation
from bot.scheduler import (
    schedule_one_off_manifestations_in,
    schedule_one_off_at_clock_time,
)

TZ = pytz.timezone("Asia/Kolkata")

# -----------------------------------------------------------------------------
# Command handlers
# -----------------------------------------------------------------------------

async def focus_cmd(update, context):
    """
    /focus [minutes] [#tag]
    Examples:
      /focus           -> 25m default
      /focus 50        -> 50m
      /focus 25 #spec  -> tag='spec'
    """
    user = update.effective_user
    chat_id = update.effective_chat.id
    args = context.args

    # defaults
    duration = 25
    tag = None
    if args:
        try:
            if args[0].isdigit():
                duration = int(args[0])
                if len(args) > 1 and args[1].startswith("#"):
                    tag = args[1][1:]
            elif args[0].startswith("#"):
                tag = args[0][1:]
                if len(args) > 1 and args[1].isdigit():
                    duration = int(args[1])
        except Exception:
            pass

    # quick commit prompt inline? keep it simple: assume commit on
    commit_phone = True
    await start_pomodoro(context.application, chat_id, user.id, duration, tag, commit_phone, ask_mid_ping=True)

async def focus_target_cmd(update, context):
    """ /focus_target 3  -> require 3 phone-free sessions/day to count towards streak """
    user = update.effective_user
    try:
        target = int(context.args[0]) if context.args else 1
        set_focus_target(user.id, max(1, target))
        await update.message.reply_text(f"Daily streak target set to {max(1, target)} phone‑free session(s).")
    except Exception as e:
        await update.message.reply_text(f"Error: {e}")

async def focus_status_cmd(update, context):
    """ Show last 7 days + current streak """
    user = update.effective_user
    daily, streak = get_focus_status(user.id)
    lines = []
    for r in daily:
        lines.append(f"{r['local_date']}: {r['sessions']} session(s), {r['phone_free_sessions']} phone‑free")
    if streak:
        lines.append(f"\nStreak: {streak['streak_days']} day(s) • Target/day: {streak['target_per_day']}")
    await update.message.reply_text("\n".join(lines) if lines else "No focus data yet.")




async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Greet and point to help."""
    await update.message.reply_text(
        "Hi! I'm your growth assistant bot.\n"
        "Try /help to see available commands."
    )
    logging.info("/start served")

async def health(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Simple liveness check with server time."""
    now = datetime.now(TZ).strftime("%Y-%m-%d %H:%M:%S %Z")
    await update.message.reply_text(f"OK ✅\nTime: {now}")
    logging.info("/health served")

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show configured chat IDs and a quick status."""
    bot_token = bool(os.getenv("BOT_TOKEN"))
    chat_id = os.getenv("CHAT_ID", "<unset>")
    chat_id_her = os.getenv("CHAT_ID_HER", "<unset>")
    now = datetime.now(TZ).strftime("%Y-%m-%d %H:%M:%S %Z")

    await update.message.reply_text(
        "Status:\n"
        f"- BOT_TOKEN set: {'yes' if bot_token else 'no'}\n"
        f"- CHAT_ID: {chat_id}\n"
        f"- CHAT_ID_HER: {chat_id_her}\n"
        f"- Server time: {now}\n"
        "Use /test_in 1 or /test_at HH:MM to verify scheduler delivery."
    )
    logging.info("/status served")

async def force_manifest(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Force-send the 3 manifestation lines for you, immediately."""
    try:
        # indexes 0,1,2 correspond to the three lines in the set
        await send_manifestation(context.application, 0)
        await send_manifestation(context.application, 1)
        await send_manifestation(context.application, 2)
        await update.message.reply_text("Sent manifestation set ✅")
    except Exception as e:
        logging.exception("force_manifest error")
        await update.message.reply_text(f"Error: {e}")

async def force_manifest_her(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Force-send the 3 manifestation lines for her, immediately."""
    try:
        await send_manifestation_for_her(context.application, 0)
        await send_manifestation_for_her(context.application, 1)
        await send_manifestation_for_her(context.application, 2)
        await update.message.reply_text("Sent manifestation set (her) ✅")
    except Exception as e:
        logging.exception("force_manifest_her error")
        await update.message.reply_text(f"Error: {e}")

async def force_card(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Force-send card prompt."""
    try:
        await send_card_prompt(context.application)
        await update.message.reply_text("Sent card prompt ✅")
    except Exception as e:
        logging.exception("force_card error")
        await update.message.reply_text(f"Error: {e}")

async def force_reveal(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Force-send card reveal."""
    try:
        await send_card_reveal(context.application)
        await update.message.reply_text("Sent card reveal ✅")
    except Exception as e:
        logging.exception("force_reveal error")
        await update.message.reply_text(f"Error: {e}")

async def clear_cache(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Clear any runtime 'used' caches if they exist, e.g. used_manifestations.json files.
    This is safe; if files don't exist, nothing happens.
    """
    from pathlib import Path

    base_dir = Path(__file__).resolve().parent
    data_dir = base_dir / "data"

    candidates = [
        data_dir / "used_manifestations.json",
        data_dir / "used_manifestations_for_her.json",
    ]

    removed = []
    for f in candidates:
        try:
            if f.exists():
                f.unlink()
                removed.append(f.name)
        except Exception as e:
            logging.warning(f"Failed to remove {f}: {e}")

    if removed:
        await update.message.reply_text("Cleared cache files: " + ", ".join(removed))
    else:
        await update.message.reply_text("No cache files found to clear.")
    logging.info("/clear_cache served")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Usage overview."""
    help_text = (
    "🧠 Vision30X Bot Help\n"
    "\n"
    "This bot delivers daily belief‑boosting manifestations and reflection cards, and helps you build\n"
    "deep‑work focus with Pomodoro sessions and streaks — inspired by Manifest, Atomic Habits, and The 5AM Club.\n"
    "\n"
    "⏱ Daily Schedule (Asia/Kolkata):\n"
    "• 08:00 — Manifestation (Line 1: Root Thought)\n"
    "• 08:15 — Manifestation (Line 2: Reframe)\n"
    "• 08:30 — Manifestation (Line 3: Reinforce)\n"
    "• 08:01/08:16/08:31 — Manifestations for Her (staggered +1 min)\n"
    "• 10:00 — Card drawn (kept hidden)\n"
    "• 19:00 — Card revealed with reflection\n"
    "\n"
    "🛠 Manual Commands:\n"
    "• /force_manifest — Send all 3 manifestations (you) now\n"
    "• /force_manifest_her — Send all 3 manifestations (her) now\n"
    "• /force_card — Pick a card immediately (kept hidden)\n"
    "• /force_reveal — Reveal the current card\n"
    "• /clear_cache — Clear today’s manifestation/card usage caches\n"
    "• /status — Show config + server time\n"
    "• /health — Quick bot liveness check\n"
    "• /start — Welcome message\n"
    "• /help — Show this help message\n"
    "\n"
    "🎯 Focus / Pomodoro (with streaks):\n"
    "• /focus — Start a 25‑minute Pomodoro (default). The bot nudges at halfway and at the end.\n"
    "• /focus 50 — Start a 50‑minute deep‑work sprint.\n"
    "• /focus 25 #spec — Start 25 minutes with an optional tag (e.g., #spec, #study, #gym).\n"
    "  At the end, tap ✅ Phone‑free or ❌ Slipped to log honesty and update your streak.\n"
    "• /focus_target <n> — Set how many phone‑free sessions/day extend your streak (default 1).\n"
    "• /focus_status — See the last 7 days of sessions and your current streak.\n"
    "\n"
    "🧪 Scheduler Tests (useful after deploy/restart):\n"
    "• /test_in <minutes> — Schedule both (you + her) one‑off manifestation runs starting in <minutes>.\n"
    "  Example: /test_in 5  → runs in ~5 minutes (staggered by ~30–60s).\n"
    "• /test_at <HH:MM> — Schedule both for today at a clock time (Asia/Kolkata), or tomorrow if passed.\n"
    "  Example: /test_at 21:35\n"
    "\n"
    "👉 Tips:\n"
    "• Keep your phone away during /focus blocks for true deep work and streak credit.\n"
    "• Use /focus_target to pick a realistic daily threshold (e.g., 2 or 3) and build consistency.\n"
    "• If the bot restarts or misses a schedule, use /test_in or /force_* commands to catch up.\n"
)

    await update.message.reply_text(help_text)
    logging.info("/help served")

# -----------------------------------------------------------------------------
# Test scheduling commands (hook into JobQueue via bot.scheduler)
# -----------------------------------------------------------------------------

async def test_in(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Example: /test_in 5  -> schedule both sets to start in 5 minutes."""
    try:
        minutes = int(context.args[0]) if context.args else 5
        schedule_one_off_manifestations_in(context.application, minutes_from_now=minutes)
        await update.message.reply_text(f"Scheduled test jobs to start in {minutes} minute(s).")
    except Exception as e:
        logging.exception("test_in error")
        await update.message.reply_text(f"Error: {e}")

async def test_at(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Example: /test_at 21:35  -> schedule both sets for 21:35 Asia/Kolkata today (or tomorrow if past)."""
    try:
        if not context.args:
            await update.message.reply_text("Usage: /test_at HH:MM (24h, Asia/Kolkata)")
            return
        hh, mm = context.args[0].split(":")
        schedule_one_off_at_clock_time(context.application, int(hh), int(mm))
        await update.message.reply_text(f"Scheduled test jobs for {context.args[0]} Asia/Kolkata.")
    except Exception as e:
        logging.exception("test_at error")
        await update.message.reply_text(f"Error: {e}")

# -----------------------------------------------------------------------------
# Registration
# -----------------------------------------------------------------------------

def setup_handlers(app: Application) -> None:
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("health", health))
    app.add_handler(CommandHandler("status", status))

    app.add_handler(CommandHandler("force_manifest", force_manifest))
    app.add_handler(CommandHandler("force_manifest_her", force_manifest_her))
    app.add_handler(CommandHandler("force_card", force_card))
    app.add_handler(CommandHandler("force_reveal", force_reveal))

    app.add_handler(CommandHandler("clear_cache", clear_cache))
    app.add_handler(CommandHandler("help", help_command))

    # Testing / scheduler helpers
    app.add_handler(CommandHandler("test_in", test_in))
    app.add_handler(CommandHandler("test_at", test_at))

    #focus handlers
    app.add_handler(CommandHandler("focus", focus_cmd))
    app.add_handler(CommandHandler("focus_target", focus_target_cmd))
    app.add_handler(CommandHandler("focus_status", focus_status_cmd))
    app.add_handler(CallbackQueryHandler(handle_phone_free_callback, pattern=r"^pfree:"))