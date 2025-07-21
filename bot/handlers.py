from telegram.ext import CommandHandler
from telegram import Update
from telegram.ext import ContextTypes
from datetime import datetime
import pytz

tz = pytz.timezone("Asia/Kolkata")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Hello! This is **PragyaBot**, your personal evolution assistant.\n\n"
        "I’ll send your daily manifestation bursts, visual affirmation cards, and help track your transformation."
    )

async def health(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("✅ Bot is running fine.")

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
