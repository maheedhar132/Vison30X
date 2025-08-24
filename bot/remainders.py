# bot/reminders.py
from __future__ import annotations

import os
from datetime import time
import pytz
from telegram.ext import Application, ContextTypes

TZ = pytz.timezone("Asia/Kolkata")

# ---------- helpers ----------

def _chat_id() -> int:
    cid = os.getenv("CHAT_ID")
    if not cid:
        raise RuntimeError("CHAT_ID env var not set")
    return int(cid)

async def _send(ctx: ContextTypes.DEFAULT_TYPE, text: str):
    await ctx.bot.send_message(chat_id=_chat_id(), text=text, disable_web_page_preview=True)

# ---------- scheduled callbacks ----------

# 🌅 Morning (7:30–8:00 AM, after PG breakfast)
async def _morning(ctx: ContextTypes.DEFAULT_TYPE):
    await _send(ctx,
        "🌅 *Morning checklist*\n"
        "• 💊 Take *Vitamin B12* (daily)\n"
        "• 💧 Drink *500ml warm water*\n"
        "• 🧴 Skincare → *Cleanser → Moisturizer (Dot & Key) → Sunscreen (Derma Co)*",
    )

# ☀️ Mid‑Morning (10:30–11:00 AM)
async def _mid_morning(ctx: ContextTypes.DEFAULT_TYPE):
    await _send(ctx,
        "☀️ *Mid‑morning*\n"
        "• 🍵 1 cup *Green Tea* (Vahdam Chamomile)\n"
        "• 💡 *Stay hydrated* — drink 1 glass of water now",
    )

# 🍛 Afternoon (Lunch – 1:30–2:00 PM)
async def _afternoon(ctx: ContextTypes.DEFAULT_TYPE):
    await _send(ctx,
        "🍛 *Afternoon (post‑lunch)*\n"
        "• 💊 Take *Iron + Zinc* tablet (Dr. Morepen)\n"
        "• ⚠️ *Avoid tea/coffee* 1 hr before/after iron",
    )

# 🌇 Evening (5:30–6:00 PM)
async def _evening(ctx: ContextTypes.DEFAULT_TYPE):
    await _send(ctx,
        "🌇 *Evening*\n"
        "• 🍵 1 cup *Green Tea* (optional, pre‑workout)\n"
        "• 🏋️‍♂️ *Get moving!* Dumbbell workout / 20‑min brisk walk",
    )

# 🌙 Night (9:30–10:00 PM, after dinner)
async def _night(ctx: ContextTypes.DEFAULT_TYPE):
    await _send(ctx,
        "🌙 *Night routine*\n"
        "• 🧴 Skincare → *Cleanser → Under‑eye cream (Minimalist) → Moisturizer (Dot & Key)*\n"
        "• 💧 Drink *last glass of water*\n"
        "• ⏰ *Lights off by 11 PM* for proper recovery",
    )

# 📅 Weekly (Sunday Morning)
async def _weekly_sunday(ctx: ContextTypes.DEFAULT_TYPE):
    await _send(ctx,
        "📅 *Weekly (Sunday)*\n"
        "• 💊 Take *Vitamin D3 + K2* capsule (Carbamide Forte)\n"
        "• ☀️ Get *15–20 min sunlight* today",
    )

# ---------- registration ----------

def setup_reminders(app: Application) -> None:
    """
    Register daily and weekly reminders.

    Times are set to the midpoint of your requested windows (Asia/Kolkata):
      • Morning:       07:45
      • Mid‑morning:   10:45
      • Afternoon:     13:45
      • Evening:       17:45
      • Night:         21:45
      • Weekly Sunday: 09:00
    Adjust below if you prefer exact minutes.
    """
    jq = app.job_queue

    # daily
    jq.run_daily(_morning,     time(hour=7,  minute=45, tzinfo=TZ), name="rem_morning")
    jq.run_daily(_mid_morning, time(hour=10, minute=45, tzinfo=TZ), name="rem_mid_morning")
    jq.run_daily(_afternoon,   time(hour=13, minute=45, tzinfo=TZ), name="rem_afternoon")
    jq.run_daily(_evening,     time(hour=17, minute=45, tzinfo=TZ), name="rem_evening")
    jq.run_daily(_night,       time(hour=21, minute=45, tzinfo=TZ), name="rem_night")

    # weekly (Sunday = 6 for python-telegram-bot run_daily's 'days' kw)
    jq.run_daily(_weekly_sunday, time(hour=9, minute=0, tzinfo=TZ), days=(6,), name="rem_weekly_sunday")
