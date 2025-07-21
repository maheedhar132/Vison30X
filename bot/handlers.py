from telegram.ext import CommandHandler
from telegram import Update
from telegram.ext import ContextTypes
from datetime import datetime
import pytz

tz = pytz.timezone("Asia/Kolkata")

# /start command
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.chat_id
    print(f"🆔 CHAT_ID = {user_id}")

    await update.message.reply_text(
        f"👋 Welcome to *PragyaBot*.\n\n"
        "I'm your personal evolution assistant.\n\n"
        f"🆔 Your Telegram chat ID is:\n`{user_id}`\n\n"
        "Paste this into your `.env` file as:\n\n"
        "`CHAT_ID={user_id}`",
        parse_mode="Markdown"
    )

# /health command
async def health(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("✅ Bot is running and alive.")

# /status command
async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    manifest = context.bot_data.get("today_manifest")
    card = context.bot_data.get("chosen_card")

    response = "📋 *Bot Status*\n"

    if manifest:
        response += f"\n🧠 Manifestation Set: ID {manifest['id']}"
        response += f"\n   → Sample: “{manifest['set'][0][:50]}...”"
    else:
        response += "\n🧠 Manifestation Set: Not selected yet today."

    if card:
        response += f"\n\n🃏 Card: *{card['title']}*"
    else:
        response += "\n\n🃏 Card: Not drawn yet today."

    now = datetime.now(tz).strftime("%Y-%m-%d %H:%M:%S")
    response += f"\n\n🕒 Time: {now} IST"

    await update.message.reply_text(response, parse_mode="Markdown")

# Setup function for main.py
def setup_handlers(app):
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("health", health))
    app.add_handler(CommandHandler("status", status))
