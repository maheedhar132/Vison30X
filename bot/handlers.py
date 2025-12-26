# bot/handlers.py

import logging
import os
from datetime import datetime
from pathlib import Path
import pytz

from telegram import Update
from telegram.ext import CommandHandler, ContextTypes, Application

from bot.manifestation import send_manifestation
from bot.manifestation_for_her import send_manifestation_for_her
from bot.cards import send_card_prompt, send_card_reveal

TZ = pytz.timezone("Asia/Kolkata")

# -------------------------------------------------------------------------
# Core system handlers
# -------------------------------------------------------------------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Vison30X is active.\n"
        "This system delivers manifestations and reflection cards.\n"
        "Use /help for available commands."
    )
    logging.info("/start served")


async def health(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    now = datetime.now(TZ).strftime("%Y-%m-%d %H:%M:%S %Z")
    await update.message.reply_text(f"OK ✅\nTime: {now}")
    logging.info("/health served")


async def status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    bot_token = bool(os.getenv("BOT_TOKEN"))
    chat_id = os.getenv("CHAT_ID", "<unset>")
    chat_id_her = os.getenv("CHAT_ID_HER", "<unset>")
    now = datetime.now(TZ).strftime("%Y-%m-%d %H:%M:%S %Z")

    await update.message.reply_text(
        "Status:\n"
        f"- BOT_TOKEN set: {'yes' if bot_token else 'no'}\n"
        f"- CHAT_ID (you): {chat_id}\n"
        f"- CHAT_ID (her): {chat_id_her}\n"
        f"- Server time: {now}"
    )
    logging.info("/status served")

# -------------------------------------------------------------------------
# Manifestations
# -------------------------------------------------------------------------

async def force_manifest(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        await send_manifestation(context.application, 0)
        await send_manifestation(context.application, 1)
        await send_manifestation(context.application, 2)
        await update.message.reply_text("Manifestations sent (you) ✅")
    except Exception as e:
        logging.exception("force_manifest error")
        await update.message.reply_text(f"Error: {e}")


async def force_manifest_her(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        await send_manifestation_for_her(context.application, 0)
        await send_manifestation_for_her(context.application, 1)
        await send_manifestation_for_her(context.application, 2)
        await update.message.reply_text("Manifestations sent (her) ✅")
    except Exception as e:
        logging.exception("force_manifest_her error")
        await update.message.reply_text(f"Error: {e}")

# -------------------------------------------------------------------------
# Cards
# -------------------------------------------------------------------------

async def force_card(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        # Draw once; cards module should persist today's card
        await send_card_prompt(context.application)
        try:
            await send_card_prompt(context.application, for_her=True)
        except TypeError:
            await send_card_prompt(context.application)

        await update.message.reply_text("Card drawn for today ✅")
    except Exception as e:
        logging.exception("force_card error")
        await update.message.reply_text(f"Error: {e}")


async def force_reveal(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        await send_card_reveal(context.application)
        try:
            await send_card_reveal(context.application, for_her=True)
        except TypeError:
            await send_card_reveal(context.application)

        await update.message.reply_text("Card revealed ✅")
    except Exception as e:
        logging.exception("force_reveal error")
        await update.message.reply_text(f"Error: {e}")

# -------------------------------------------------------------------------
# Maintenance
# -------------------------------------------------------------------------

async def clear_cache(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    base_dir = Path(__file__).resolve().parent
    data_dir = base_dir / "data"

    candidates = [
        data_dir / "used_manifestations.json",
        data_dir / "used_manifestations_for_her.json",
        data_dir / "today_manifestation.json",
        data_dir / "today_card.json",
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
        await update.message.reply_text("Cleared cache: " + ", ".join(removed))
    else:
        await update.message.reply_text("No cache files found.")
    logging.info("/clear_cache served")

# -------------------------------------------------------------------------
# Help
# -------------------------------------------------------------------------

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    help_text = (
        "🧠 Vison30X — Reflection System\n\n"
        "This system delivers:\n"
        "• Daily manifestations (3-line sequence)\n"
        "• Daily reflection card (draw → reveal)\n\n"
        "Manual commands:\n"
        "• /force_manifest — Send all 3 manifestations (you)\n"
        "• /force_manifest_her — Send all 3 manifestations (her)\n"
        "• /force_card — Draw today’s card (hidden)\n"
        "• /force_reveal — Reveal today’s card\n"
        "• /clear_cache — Clear today’s runtime state\n"
        "• /status — System configuration\n"
        "• /health — Liveness check\n"
        "• /help — This message\n"
    )
    await update.message.reply_text(help_text)
    logging.info("/help served")

# -------------------------------------------------------------------------
# Registration
# -------------------------------------------------------------------------

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

    logging.info("Handlers setup complete (core only).")
