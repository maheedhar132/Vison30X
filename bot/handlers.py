# bot/handlers.py

from __future__ import annotations

import logging
import os
import traceback
from datetime import datetime
import pytz

from telegram import Update
from telegram.ext import CommandHandler, ContextTypes, Application

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
        "Commands:\n"
        "/start – greet\n"
        "/health – liveness check\n"
        "/status – show config/time\n"
        "/force_manifest – send today's manifestation set (you) now\n"
        "/force_manifest_her – send today's manifestation set (her) now\n"
        "/force_card – send card prompt now\n"
        "/force_reveal – send card reveal now\n"
        "/clear_cache – delete runtime used_* caches if present\n"
        "/test_in <minutes> – schedule both (you + her) one‑off tests starting in <minutes>\n"
        "/test_at <HH:MM> – schedule both (you + her) today at HH:MM Asia/Kolkata (or tomorrow if passed)\n"
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
