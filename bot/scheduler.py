# bot/scheduler.py

from datetime import time, datetime, timedelta
import pytz
from telegram.ext import Application, ContextTypes

from bot.manifestation import send_manifestation
from bot.manifestation_for_her import send_manifestation_for_her
from bot.cards import send_card_prompt, send_card_reveal

TZ = pytz.timezone("Asia/Kolkata")

# ---- JobQueue callbacks (async) ----

async def _job_manifestation_0(context: ContextTypes.DEFAULT_TYPE) -> None:
    await send_manifestation(context.application, 0)

async def _job_manifestation_1(context: ContextTypes.DEFAULT_TYPE) -> None:
    await send_manifestation(context.application, 1)

async def _job_manifestation_2(context: ContextTypes.DEFAULT_TYPE) -> None:
    await send_manifestation(context.application, 2)

async def _job_manifestation_her_0(context: ContextTypes.DEFAULT_TYPE) -> None:
    await send_manifestation_for_her(context.application, 0)

async def _job_manifestation_her_1(context: ContextTypes.DEFAULT_TYPE) -> None:
    await send_manifestation_for_her(context.application, 1)

async def _job_manifestation_her_2(context: ContextTypes.DEFAULT_TYPE) -> None:
    await send_manifestation_for_her(context.application, 2)

async def _job_card_prompt(context: ContextTypes.DEFAULT_TYPE) -> None:
    await send_card_prompt(context.application)

async def _job_card_reveal(context: ContextTypes.DEFAULT_TYPE) -> None:
    await send_card_reveal(context.application)

def setup_jobs(app: Application) -> None:
    """
    Register recurring jobs on PTB's JobQueue.
    No explicit .start(); Application manages the JobQueue lifecycle.
    """
    jq = app.job_queue

    # --- Manifestations (you) at 08:00 / 08:15 / 08:30 ---
    jq.run_daily(_job_manifestation_0, time(hour=8, minute=0, tzinfo=TZ),  name="manifestation_0")
    jq.run_daily(_job_manifestation_1, time(hour=8, minute=15, tzinfo=TZ), name="manifestation_1")
    jq.run_daily(_job_manifestation_2, time(hour=8, minute=30, tzinfo=TZ), name="manifestation_2")

    # --- Manifestations for Her, staggered by +1 minute: 08:01 / 08:16 / 08:31 ---
    jq.run_daily(_job_manifestation_her_0, time(hour=8, minute=1, tzinfo=TZ),  name="manifestation_her_0")
    jq.run_daily(_job_manifestation_her_1, time(hour=8, minute=16, tzinfo=TZ), name="manifestation_her_1")
    jq.run_daily(_job_manifestation_her_2, time(hour=8, minute=31, tzinfo=TZ), name="manifestation_her_2")

    # --- Cards (unchanged) ---
    jq.run_daily(_job_card_prompt, time(hour=10, minute=0, tzinfo=TZ), name="card_prompt")
    jq.run_daily(_job_card_reveal, time(hour=19, minute=0, tzinfo=TZ), name="card_reveal")

# -------- One-off testing utilities --------

def schedule_one_off_manifestations_in(app: Application, minutes_from_now: int = 5) -> None:
    """
    Schedule both your manifestation[0..2] and her manifestation[0..2] to run once,
    starting minutes_from_now and spaced by 1 minute.
    """
    jq = app.job_queue
    now = datetime.now(TZ)
    t0 = now + timedelta(minutes=minutes_from_now)
    jq.run_once(_job_manifestation_0, when=t0, name="test_manifestation_0")
    jq.run_once(_job_manifestation_1, when=t0 + timedelta(minutes=1), name="test_manifestation_1")
    jq.run_once(_job_manifestation_2, when=t0 + timedelta(minutes=2), name="test_manifestation_2")

    jq.run_once(_job_manifestation_her_0, when=t0 + timedelta(minutes=0, seconds=30), name="test_manifestation_her_0")
    jq.run_once(_job_manifestation_her_1, when=t0 + timedelta(minutes=1, seconds=30), name="test_manifestation_her_1")
    jq.run_once(_job_manifestation_her_2, when=t0 + timedelta(minutes=2, seconds=30), name="test_manifestation_her_2")

def schedule_one_off_at_clock_time(app: Application, hh: int, mm: int) -> None:
    """
    Schedule both sets to run once at today's Asia/Kolkata time hh:mm
    (use this for e.g. 21:35 tests).
    """
    jq = app.job_queue
    now = datetime.now(TZ)
    at = TZ.localize(datetime(now.year, now.month, now.day, hh, mm, 0))
    if at <= now:
        # If the time has already passed today, schedule for tomorrow same time
        at = at + timedelta(days=1)

    jq.run_once(_job_manifestation_0, when=at, name="at_manifestation_0")
    jq.run_once(_job_manifestation_1, when=at + timedelta(minutes=1), name="at_manifestation_1")
    jq.run_once(_job_manifestation_2, when=at + timedelta(minutes=2), name="at_manifestation_2")

    jq.run_once(_job_manifestation_her_0, when=at + timedelta(minutes=0, seconds=30), name="at_manifestation_her_0")
    jq.run_once(_job_manifestation_her_1, when=at + timedelta(minutes=1, seconds=30), name="at_manifestation_her_1")
    jq.run_once(_job_manifestation_her_2, when=at + timedelta(minutes=2, seconds=30), name="at_manifestation_her_2")
