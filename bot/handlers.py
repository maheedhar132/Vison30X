from telegram import Update
from telegram.ext import CommandHandler, ContextTypes
from datetime import datetime
import pytz
import logging
import os

from bot.manifestation import send_manifestation
from bot.cards import send_card_prompt, send_card_reveal

tz = pytz.timezone("Asia/Kolkata")

# Logging setup
LOG_DIR = "/var/log/vision30x"
os.makedirs(LOG_DIR, exist_ok=True)
logging.basicConfig(
    filename=os.path.join(LOG_DIR, "bot.log"),
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_chat.id
    await update.message.reply_text(
        f"Welcome to Vision30X Bot!\n\nYour chat ID:\n`{user_id}`\n\nPaste it into your `.env` file as:\n\n`CHAT_ID={user_id}`",
        parse_mode="Markdown"
    )
    logging.info(f"/start used by chat_id {user_id}")

async def health(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("✅ Bot is alive and responding.")
    logging.info("/health command acknowledged.")

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    manifest = context.bot_data.get("today_manifest")
    card = context.bot_data.get("chosen_card")
    now = datetime.now(tz).strftime("%Y-%m-%d %H:%M:%S")

    msg = f"📋 *Vision30X Status*\n\n🕒 {now} IST\n"

    if manifest:
        msg += f"\n🧠 Manifest ID: {manifest['id']}\n→ “{manifest['set'][0][:40]}...”"
    else:
        msg += "\n🧠 Manifestation: Not yet picked."

    if card:
        msg += f"\n\n🃏 Card: *{card['title']}*"
    else:
        msg += "\n\n🃏 Card: Not drawn yet."

    await update.message.reply_text(msg, parse_mode="Markdown")
    logging.info("Status command responded.")

async def force_manifest(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("⏱ Sending 3 manifestations...")
    logging.info("Manual trigger: /force_manifest")
    try:
        for i in range(3):
            await send_manifestation(context.application, i)
    except Exception as e:
        logging.error(f"Error in /force_manifest: {e}")
        await update.message.reply_text("❌ Failed to send manifestations.")

async def force_card(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        send_card_prompt(context.application)
        await update.message.reply_text("🃏 Card prompt sent.")
        logging.info("/force_card used.")
    except Exception as e:
        logging.error(f"Error in /force_card: {e}")
        await update.message.reply_text("❌ Failed to draw card.")

async def force_reveal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        send_card_reveal(context.application)
        await update.message.reply_text("🔮 Card revealed.")
        logging.info("/force_reveal used.")
    except Exception as e:
        logging.error(f"Error in /force_reveal: {e}")
        await update.message.reply_text("❌ Failed to reveal card.")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🧠 *Vision30X Bot Help*\n\n"
        "This bot sends daily belief-boosting messages and affirmation cards inspired by elite mindset rituals.\n\n"
        "⏱ *Daily Schedule:*\n"
        "• 9:00 AM - Manifestation (Root Thought)\n"
        "• 9:15 AM - Manifestation (Reframe)\n"
        "• 9:30 AM - Manifestation (Reinforce)\n"
        "• 10:00 AM - Card drawn (kept hidden)\n"
        "• 7:00 PM - Card revealed with reflection\n\n"
        "🛠 *Manual Commands:*\n"
        "• `/force_manifest` — Send all 3 manifestations now\n"
        "• `/force_card` — Pick a card immediately (remains hidden)\n"
        "• `/force_reveal` — Reveal the current card\n"
        "• `/status` — See today's manifestation/card\n"
        "• `/health` — Ping the bot to check if it's live\n"
        "• `/start` — Get your CHAT_ID for config\n"
        "• `/help` — Show this message\n\n"
        "_Use manual commands if the bot restarted mid-day or missed a scheduled message._",
        parse_mode="Markdown"
    )
    logging.info("Help command served.")

def setup_handlers(app):
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("health", health))
    app.add_handler(CommandHandler("status", status))
    app.add_handler(CommandHandler("force_manifest", force_manifest))
    app.add_handler(CommandHandler("force_card", force_card))
    app.add_handler(CommandHandler("force_reveal", force_reveal))
    app.add_handler(CommandHandler("help", help_command))
