# bot/db.py
from __future__ import annotations
import sqlite3, os, pathlib, contextlib
from datetime import datetime, date
from typing import Optional, Tuple

DB_PATH = os.getenv("V30X_DB", str(pathlib.Path(__file__).resolve().parent / "data" / "vison30x.db"))
pathlib.Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)

def connect():
    conn = sqlite3.connect(DB_PATH, detect_types=sqlite3.PARSE_DECLTYPES)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with connect() as db:
        db.executescript("""
        PRAGMA journal_mode=WAL;

        CREATE TABLE IF NOT EXISTS users (
          user_id      INTEGER PRIMARY KEY,
          chat_id      INTEGER NOT NULL,
          display_name TEXT,
          role         TEXT CHECK(role IN ('self','partner','guest')) DEFAULT 'self',
          created_at   DATETIME DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS focus_sessions (
          id            INTEGER PRIMARY KEY AUTOINCREMENT,
          user_id       INTEGER NOT NULL,
          started_at_utc DATETIME NOT NULL,
          duration_min  INTEGER NOT NULL,
          tag           TEXT,
          phone_commit  INTEGER DEFAULT 0,   -- 1 if user committed to phone away
          phone_free    INTEGER,             -- 1 yes, 0 no, NULL not answered yet
          completed     INTEGER DEFAULT 0,   -- 1 when session finished
          notes         TEXT,
          created_at    DATETIME DEFAULT CURRENT_TIMESTAMP,
          FOREIGN KEY (user_id) REFERENCES users(user_id)
        );

        CREATE INDEX IF NOT EXISTS idx_focus_user_started ON focus_sessions(user_id, started_at_utc);

        -- Daily counters (normalized by local date Asia/Kolkata on insert/update)
        CREATE TABLE IF NOT EXISTS focus_daily (
          user_id      INTEGER NOT NULL,
          local_date   DATE NOT NULL,
          sessions     INTEGER NOT NULL DEFAULT 0,
          phone_free_sessions INTEGER NOT NULL DEFAULT 0,
          PRIMARY KEY (user_id, local_date)
        );

        -- Streak of consecutive days meeting target_per_day phone-free sessions (or any sessions if you prefer)
        CREATE TABLE IF NOT EXISTS focus_streaks (
          user_id       INTEGER PRIMARY KEY,
          target_per_day INTEGER NOT NULL DEFAULT 1,
          last_date     DATE,
          streak_days   INTEGER NOT NULL DEFAULT 0
        );
        """)

def upsert_user(user_id: int, chat_id: int, display_name: Optional[str], role: str = "self"):
    with connect() as db:
        db.execute("""
            INSERT INTO users(user_id, chat_id, display_name, role)
            VALUES(?,?,?,?)
            ON CONFLICT(user_id) DO UPDATE SET chat_id=excluded.chat_id, display_name=excluded.display_name
        """, (user_id, chat_id, display_name, role))

def start_focus_session(user_id: int, duration_min: int, tag: Optional[str], phone_commit: bool) -> int:
    with connect() as db:
        cur = db.execute("""
          INSERT INTO focus_sessions(user_id, started_at_utc, duration_min, tag, phone_commit)
          VALUES(?, datetime('now'), ?, ?, ?)
        """, (user_id, duration_min, tag, 1 if phone_commit else 0))
        return cur.lastrowid

def complete_focus_session(session_id: int, phone_free: Optional[bool], notes: Optional[str]) -> Tuple[int, int]:
    """
    Marks session completed and updates focus_daily counters based on Asia/Kolkata local date of 'now'.
    Returns (sessions_today, phone_free_sessions_today) for that user.
    """
    from zoneinfo import ZoneInfo
    IST = ZoneInfo("Asia/Kolkata")

    with connect() as db:
        # fetch session
        r = db.execute("SELECT user_id FROM focus_sessions WHERE id = ?", (session_id,)).fetchone()
        if not r:
            return (0,0)
        user_id = r["user_id"]

        db.execute("""
          UPDATE focus_sessions
             SET completed=1,
                 phone_free = CASE
                     WHEN ? IS NULL THEN phone_free
                     ELSE CASE WHEN ? THEN 1 ELSE 0 END
                 END,
                 notes = COALESCE(?, notes)
           WHERE id = ?
        """, (None if phone_free is None else 1, True if phone_free else False, notes, session_id))

        # compute today's local date in IST
        today_local = datetime.now(IST).date()

        # ensure daily row
        db.execute("""
          INSERT INTO focus_daily(user_id, local_date, sessions, phone_free_sessions)
          VALUES(?, ?, 0, 0)
          ON CONFLICT(user_id, local_date) DO NOTHING
        """, (user_id, today_local))

        # increment counts
        if phone_free is None:
            db.execute("""UPDATE focus_daily SET sessions = sessions + 1 WHERE user_id=? AND local_date=?""",
                       (user_id, today_local))
        else:
            db.execute("""
              UPDATE focus_daily
                 SET sessions = sessions + 1,
                     phone_free_sessions = phone_free_sessions + ?
               WHERE user_id=? AND local_date=?""",
               (1 if phone_free else 0, user_id, today_local))

        # fetch updated counts
        row = db.execute("""SELECT sessions, phone_free_sessions FROM focus_daily WHERE user_id=? AND local_date=?""",
                         (user_id, today_local)).fetchone()

        # update streaks: require at least target_per_day phone-free sessions
        s = db.execute("""SELECT target_per_day, last_date, streak_days FROM focus_streaks WHERE user_id=?""",
                       (user_id,)).fetchone()
        target = s["target_per_day"] if s else 1
        last_date = date.fromisoformat(s["last_date"]) if (s and s["last_date"]) else None
        streak_days = s["streak_days"] if s else 0

        # if first record for user
        if not s:
            db.execute("INSERT INTO focus_streaks(user_id, target_per_day, last_date, streak_days) VALUES(?,?,?,?)",
                       (user_id, target, None, 0))

        # Only recompute streak end-of-day normally; for simplicity we update if threshold reached today
        if row["phone_free_sessions"] >= target:
            # consecutive?
            if last_date is None or last_date == today_local or last_date == today_local.replace(day=today_local.day-1):
                # If last_date == today, keep streak_days as-is; else increment
                if last_date != today_local:
                    streak_days += 1
                db.execute("""UPDATE focus_streaks SET last_date=?, streak_days=? WHERE user_id=?""",
                           (today_local.isoformat(), streak_days, user_id))
            else:
                # gap, reset to 1
                streak_days = 1
                db.execute("""UPDATE focus_streaks SET last_date=?, streak_days=? WHERE user_id=?""",
                           (today_local.isoformat(), streak_days, user_id))

        return (row["sessions"], row["phone_free_sessions"])

def get_focus_status(user_id: int):
    with connect() as db:
        daily = db.execute("""
            SELECT local_date, sessions, phone_free_sessions
              FROM focus_daily
             WHERE user_id=?
             ORDER BY local_date DESC
             LIMIT 7
        """, (user_id,)).fetchall()
        streak = db.execute("SELECT target_per_day, last_date, streak_days FROM focus_streaks WHERE user_id=?", (user_id,)).fetchone()
        return daily, streak

def set_focus_target(user_id: int, target_per_day: int):
    with connect() as db:
        db.execute("""
          INSERT INTO focus_streaks(user_id, target_per_day, last_date, streak_days)
          VALUES(?,?,NULL,0)
          ON CONFLICT(user_id) DO UPDATE SET target_per_day=excluded.target_per_day
        """, (user_id, target_per_day))
