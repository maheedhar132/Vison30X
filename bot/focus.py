# bot/focus.py
from __future__ import annotations
from dataclasses import dataclass
from telegram.ext import ContextTypes
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from bot.db import start_focus_session, complete_focus_session, upsert_user

@dataclass
class FocusJobData:
    session_id: int
    user_id: int
    duration: int
    tag: str | None

# Ask commitment, then start timer
async def start_pomodoro(app, chat_id: int, user_id: int, duration_min: int, tag: str | None, commit_phone: bool, ask_mid_ping: bool = True):
    upsert_user(user_id=user_id, chat_id=chat_id, display_name=None)
    session_id = start_focus_session(user_id, duration_min, tag, commit_phone)

    await app.bot.send_message(
        chat_id,
        f"🎯 Focus started ({duration_min}m){' • ' + tag if tag else ''}\n"
        f"{'📵 Phone away, please.' if commit_phone else ''}"
    )

    # mid ping at half time
    if ask_mid_ping and duration_min >= 20:
        app.job_queue.run_once(_mid_ping, when=duration_min*30, data=FocusJobData(session_id, user_id, duration_min, tag), name=f"focus_mid_{session_id}")

    # end ping
    app.job_queue.run_once(_end_ping, when=duration_min*60, data=FocusJobData(session_id, user_id, duration_min, tag), name=f"focus_end_{session_id}")

async def _mid_ping(context: ContextTypes.DEFAULT_TYPE):
    jd: FocusJobData = context.job.data
    await context.bot.send_message(
        chat_id=(await context.bot.get_chat(jd.user_id)).id if False else jd.user_id,
        text="⏳ Halfway. Breathe. Stay with the task. 📵"
    )

async def _end_ping(context: ContextTypes.DEFAULT_TYPE):
    jd: FocusJobData = context.job.data
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ Phone‑free", callback_data=f"pfree:1:{jd.session_id}"),
        InlineKeyboardButton("❌ Slipped", callback_data=f"pfree:0:{jd.session_id}")
    ]])
    await context.bot.send_message(
        jd.user_id,
        "⏰ Pomodoro complete! Mark honesty for streak:",
        reply_markup=kb
    )

# Callback-query handler to record phone_free and update streak/counters
async def handle_phone_free_callback(update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    try:
        _, flag, sid = q.data.split(":")
        phone_free = True if flag == "1" else False
        sessions, pfree_sessions = complete_focus_session(int(sid), phone_free, None)
        await q.edit_message_text(f"Logged: {'✅ Phone‑free' if phone_free else '❌ Slipped'}\n"
                                  f"Today: {sessions} sessions • {pfree_sessions} phone‑free")
    except Exception as e:
        await q.edit_message_text(f"Error logging session: {e}")
