from telegram import Update
from telegram.ext import CommandHandler, ContextTypes
from datetime import datetime
import pytz

from bot.manifestation import send_manifestation
from bot.cards import send_card_prompt, send_card_reveal

tz = pytz.timezone("Asia/Kolkata")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_chat.id
    await update.message.reply_text(
        f"Welcome to Vision30X Bot!\n\nYour chat ID:\n`{user_id}`\n\nPaste it into your `.env` file as:\n\n`CHAT_ID={user_id}`",
        parse_mode="Markdown"
    )

async def health(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("✅ Bot is alive and responding.")

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

async def force_manifest(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("⏱ Sending 3 manifestations...")
    for i in range(3):
        send_manifestation(context.application, i)

async def force_card(update: Update, context: ContextTypes.DEFAULT_TYPE):
    send_card_prompt(context.application)
    await update.message.reply_text("🃏 Card prompt sent.")

async def force_reveal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    send_card_reveal(context.application)
    await update.message.reply_text("🔮 Card revealed.")

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

def setup_handlers(app):
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("health", health))
    app.add_handler(CommandHandler("status", status))
    app.add_handler(CommandHandler("force_manifest", force_manifest))
    app.add_handler(CommandHandler("force_card", force_card))
    app.add_handler(CommandHandler("force_reveal", force_reveal))
    app.add_handler(CommandHandler("help", help_command))
