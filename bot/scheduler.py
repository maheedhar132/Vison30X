# bot/scheduler.py
"""
Scheduler for Vision30X.

Responsibilities:
- Register recurring daily jobs for manifestations (you + her), cards (draw + reveal for both),
  and health/lifestyle reminders (morning/mid/lunch/evening/night + weekly vitamin D).
- Expose one-off test helpers used by /test_in and /test_at.
- Be defensive if optional modules/functions are missing (e.g. bot.reminders or for_her variants).
"""

from datetime import datetime, timedelta, time
import logging
import pytz
import os

from telegram.ext import Application, ContextTypes

# Core actions from project (expected to exist)
from bot.manifestation import send_manifestation
from bot.manifestation_for_her import send_manifestation_for_her
from bot.cards import send_card_prompt, send_card_reveal

TZ = pytz.timezone(os.getenv("V30X_TZ", "Asia/Kolkata"))

# Optional reminders module (may not exist yet)
try:
    from bot.reminders import send_reminder, send_weekly_reminder
except Exception:
    send_reminder = None
    send_weekly_reminder = None

# Helper to attempt calling a "for_her" variant if available otherwise fallback
async def _call_maybe_for_her(func, app: Application, *, for_her: bool = False, **kwargs):
    """
    Try to call func(app, **kwargs). If for_her True and func accepts a 'for_her' kw, pass it.
    If an alternative function named func.__name__ + '_for_her' exists in same module, use it.
    """
    # If nothing to call, return
    if not func:
        logging.debug("_call_maybe_for_her: no function provided")
        return

    # If caller specifically passed a 'for_her' kw, try that first
    try:
        # First try calling with for_her kw (if the function supports it)
        kwargs_try = dict(kwargs)
        if for_her:
            kwargs_try["for_her"] = True
        await func(app, **kwargs_try)
        return
    except TypeError:
        # function doesn't accept for_her kw or some other signature difference; fallthrough
        pass
    except Exception as ex:
        # Unexpected error while calling — log and return
        logging.exception("Error calling function (first attempt): %s", ex)
        return

    # Next: attempt to locate sibling function named <name>_for_her in calling module
    try:
        module = func.__module__
        name = func.__name__ + "_for_her"
        mod = __import__(module, fromlist=[name])
        alt = getattr(mod, name, None)
        if alt:
            await alt(app, **kwargs)
            return
    except Exception:
        # ignore and fallback
        pass

    # Final fallback: call same function without for_her (idempotent implementations should reuse stored state)
    try:
        await func(app, **kwargs)
    except Exception as ex:
        logging.exception("Final fallback call failed: %s", ex)


# -------------------------
# Job callbacks
# -------------------------

# Manifestations (you) index callbacks
async def _job_manifestation_0(context: ContextTypes.DEFAULT_TYPE) -> None:
    await send_manifestation(context.application, 0)

async def _job_manifestation_1(context: ContextTypes.DEFAULT_TYPE) -> None:
    await send_manifestation(context.application, 1)

async def _job_manifestation_2(context: ContextTypes.DEFAULT_TYPE) -> None:
    await send_manifestation(context.application, 2)

# Manifestations (her) index callbacks
async def _job_manifestation_her_0(context: ContextTypes.DEFAULT_TYPE) -> None:
    # prefer dedicated for-her function if present
    try:
        await send_manifestation_for_her(context.application, 0)
    except Exception:
        # fallback to calling the normal send_manifestation (it may accept a for_her flag or be idempotent)
        try:
            await send_manifestation(context.application, 0)
        except Exception:
            logging.exception("Failed to send manifestation for her (index 0)")

async def _job_manifestation_her_1(context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        await send_manifestation_for_her(context.application, 1)
    except Exception:
        try:
            await send_manifestation(context.application, 1)
        except Exception:
            logging.exception("Failed to send manifestation for her (index 1)")

async def _job_manifestation_her_2(context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        await send_manifestation_for_her(context.application, 2)
    except Exception:
        try:
            await send_manifestation(context.application, 2)
        except Exception:
            logging.exception("Failed to send manifestation for her (index 2)")

# Card draw/reveal callbacks (for you + her via _call_maybe_for_her)
async def _job_card_prompt(context: ContextTypes.DEFAULT_TYPE) -> None:
    # draw for you
    await _call_maybe_for_her(send_card_prompt, context.application, for_her=False)
    # draw for her (attempt)
    await _call_maybe_for_her(send_card_prompt, context.application, for_her=True)

async def _job_card_reveal(context: ContextTypes.DEFAULT_TYPE) -> None:
    # reveal for you
    await _call_maybe_for_her(send_card_reveal, context.application, for_her=False)
    # reveal for her
    await _call_maybe_for_her(send_card_reveal, context.application, for_her=True)

# Reminders callback wrapper
async def _job_send_reminder(context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Generic wrapper that expects context.job.data to contain:
      - key: 'slot' (one of 'morning','mid_morning','lunch','evening','night'), optional 'weekly' for weekly reminders
    """
    if not send_reminder:
        logging.debug("No bot.reminders module available; skipping reminder job.")
        return

    try:
        data = context.job.data or {}
        slot = data.get("slot")
        await send_reminder(context.application, slot)
    except Exception:
        logging.exception("Reminder job failed.")


async def _job_send_weekly_reminder(context: ContextTypes.DEFAULT_TYPE) -> None:
    if not send_weekly_reminder:
        logging.debug("No bot.reminders.send_weekly_reminder available; skipping weekly reminder job.")
        return
    try:
        data = context.job.data or {}
        key = data.get("key")
        await send_weekly_reminder(context.application, key=key)
    except Exception:
        logging.exception("Weekly reminder job failed.")


# -------------------------
# Schedule registration
# -------------------------

def _env_time(name: str, default_h: int, default_m: int) -> time:
    """
    Read time from environment variable V30X_<name> in HH:MM format (24h).
    Example: V30X_MANIFEST_0=08:00
    """
    key = f"V30X_{name}"
    raw = os.getenv(key)
    if raw:
        try:
            hh, mm = raw.split(":")
            return time(hour=int(hh), minute=int(mm), tzinfo=TZ)
        except Exception:
            logging.warning("Invalid time in %s: %s. Using default.", key, raw)
    return time(hour=default_h, minute=default_m, tzinfo=TZ)


def setup_jobs(app: Application) -> None:
    """
    Register recurring jobs on PTB's JobQueue.
    - Manifestations for you: three daily times (defaults 08:00 / 08:15 / 08:30)
    - Manifestations for her: staggered by +1 minute by default
    - Card draw: 10:00 (default) draw + 19:00 reveal
    - Reminders: multiple daily slots and a weekly Sunday reminder
    """
    jq = app.job_queue

    # --- manifest times configurable through env ---
    m0 = _env_time("MANIFEST_0", 8, 0)
    m1 = _env_time("MANIFEST_1", 8, 15)
    m2 = _env_time("MANIFEST_2", 8, 30)

    # her offset (minutes). default 1 => 08:01/08:16/08:31
    try:
        her_offset = int(os.getenv("V30X_MANIFEST_HER_OFFSET", "1"))
    except Exception:
        her_offset = 1

    # schedule your manifestations
    jq.run_daily(_job_manifestation_0, m0, name="manifestation_0")
    jq.run_daily(_job_manifestation_1, m1, name="manifestation_1")
    jq.run_daily(_job_manifestation_2, m2, name="manifestation_2")

    # her times (shift minutes by her_offset)
    def _shift_time(t: time, mins: int) -> time:
        # convert to datetime today then shift
        now = datetime.now(TZ)
        dt = TZ.localize(datetime(now.year, now.month, now.day, t.hour, t.minute, 0))
        dt_shift = dt + timedelta(minutes=mins)
        return time(hour=dt_shift.hour, minute=dt_shift.minute, tzinfo=TZ)

    jq.run_daily(_job_manifestation_her_0, _shift_time(m0, her_offset), name="manifestation_her_0")
    jq.run_daily(_job_manifestation_her_1, _shift_time(m1, her_offset), name="manifestation_her_1")
    jq.run_daily(_job_manifestation_her_2, _shift_time(m2, her_offset), name="manifestation_her_2")

    # --- Cards (defaults can be configured) ---
    card_draw_time = _env_time("CARD_DRAW", 10, 0)
    card_reveal_time = _env_time("CARD_REVEAL", 19, 0)

    jq.run_daily(_job_card_prompt, card_draw_time, name="card_prompt")
    jq.run_daily(_job_card_reveal, card_reveal_time, name="card_reveal")

    # --- Reminders (health & lifestyle) ---
    # Slots (defaults)
    morning_time = _env_time("REMINDER_MORNING", 7, 35)     # ~ after breakfast window
    mid_morning_time = _env_time("REMINDER_MID_MORNING", 10, 45)
    lunch_time = _env_time("REMINDER_LUNCH", 13, 45)
    evening_time = _env_time("REMINDER_EVENING", 17, 45)
    night_time = _env_time("REMINDER_NIGHT", 21, 45)
    # Weekly vitamin D (Sunday)
    weekly_vitamin_time = _env_time("REMINDER_WEEKLY", 9, 0)

    # attach jobs if reminders module exists; otherwise they're no-ops (and logged)
    jq.run_daily(_job_send_reminder, morning_time, name="reminder_morning", days=None, data={"slot": "morning"})
    jq.run_daily(_job_send_reminder, mid_morning_time, name="reminder_mid_morning", days=None, data={"slot": "mid_morning"})
    jq.run_daily(_job_send_reminder, lunch_time, name="reminder_lunch", days=None, data={"slot": "lunch"})
    jq.run_daily(_job_send_reminder, evening_time, name="reminder_evening", days=None, data={"slot": "evening"})
    jq.run_daily(_job_send_reminder, night_time, name="reminder_night", days=None, data={"slot": "night"})

    # weekly vitamin D on Sundays (weekday=6)
    # NOTE: run_daily accepts days parameter in PTB; pass (6,) to schedule only Sundays.
    try:
        jq.run_daily(_job_send_weekly_reminder, weekly_vitamin_time, days=(6,), name="reminder_weekly_vitamin", data={"key": "vitamin_d"})
    except TypeError:
        # older PTB versions may accept 'days' differently; best-effort fallback: schedule daily but the reminder function can check weekday.
        jq.run_daily(_job_send_weekly_reminder, weekly_vitamin_time, name="reminder_weekly_vitamin", data={"key": "vitamin_d"})

    logging.info("Scheduler: jobs registered (manifestations, cards, reminders).")


# -------- One-off testing utilities --------

def schedule_one_off_manifestations_in(app: Application, minutes_from_now: int = 5) -> None:
    """
    Schedule both your manifestation[0..2] and her manifestation[0..2] to run once,
    starting minutes_from_now and spaced by 1 minute.
    """
    jq = app.job_queue
    now = datetime.now(TZ)
    t0 = now + timedelta(minutes=minutes_from_now)
    # you (0,1,2) spaced 0,1,2 minutes
    jq.run_once(_job_manifestation_0, when=t0, name="test_manifestation_0")
    jq.run_once(_job_manifestation_1, when=t0 + timedelta(minutes=1), name="test_manifestation_1")
    jq.run_once(_job_manifestation_2, when=t0 + timedelta(minutes=2), name="test_manifestation_2")

    # her (stagger a bit: offset 30s)
    jq.run_once(_job_manifestation_her_0, when=t0 + timedelta(seconds=30), name="test_manifestation_her_0")
    jq.run_once(_job_manifestation_her_1, when=t0 + timedelta(minutes=1, seconds=30), name="test_manifestation_her_1")
    jq.run_once(_job_manifestation_her_2, when=t0 + timedelta(minutes=2, seconds=30), name="test_manifestation_her_2")

    # also schedule card draw/reveal for test (draw at t0+3min, reveal at t0+4min)
    jq.run_once(_job_card_prompt, when=t0 + timedelta(minutes=3), name="test_card_prompt")
    jq.run_once(_job_card_reveal, when=t0 + timedelta(minutes=4), name="test_card_reveal")

def schedule_one_off_at_clock_time(app: Application, hh: int, mm: int) -> None:
    """
    Schedule both sets to run once at today's Asia/Kolkata time hh:mm
    (use this for e.g. 21:35 tests). If time already passed today, schedule for tomorrow.
    """
    jq = app.job_queue
    now = datetime.now(TZ)
    at = TZ.localize(datetime(now.year, now.month, now.day, hh, mm, 0))
    if at <= now:
        at = at + timedelta(days=1)

    jq.run_once(_job_manifestation_0, when=at, name="at_manifestation_0")
    jq.run_once(_job_manifestation_1, when=at + timedelta(minutes=1), name="at_manifestation_1")
    jq.run_once(_job_manifestation_2, when=at + timedelta(minutes=2), name="at_manifestation_2")

    jq.run_once(_job_manifestation_her_0, when=at + timedelta(seconds=30), name="at_manifestation_her_0")
    jq.run_once(_job_manifestation_her_1, when=at + timedelta(minutes=1, seconds=30), name="at_manifestation_her_1")
    jq.run_once(_job_manifestation_her_2, when=at + timedelta(minutes=2, seconds=30), name="at_manifestation_her_2")

    # Also schedule card prompt + reveal around the same window
    jq.run_once(_job_card_prompt, when=at + timedelta(minutes=3), name="at_card_prompt")
    jq.run_once(_job_card_reveal, when=at + timedelta(minutes=4), name="at_card_reveal")

