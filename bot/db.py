# bot/db.py
from __future__ import annotations

import sqlite3
import os
import pathlib
from datetime import datetime, date
from typing import Optional, Tuple

# ---------------------------------------------------------------------
# Database path
# ---------------------------------------------------------------------
DB_PATH = os.getenv(
    "V30X_DB",
    str(pathlib.Path(__file__).resolve().parent / "data" / "vison30x.db"),
)

pathlib.Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------
# Connection helper (SINGLE source of truth)
# ---------------------------------------------------------------------
def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, detect_types=sqlite3.PARSE_DECLTYPES)
    conn.row_factory = sqlite3.Row
    return conn

# ---------------------------------------------------------------------
# Init DB schema (idempotent)
# ---------------------------------------------------------------------
def init_db():
    with connect() as db:
        db.executescript("""
        PRAGMA journal_mode=WAL;

        -- Users
        CREATE TABLE IF NOT EXISTS users (
          user_id      INTEGER PRIMARY KEY,
          chat_id      INTEGER NOT NULL,
          display_name TEXT,
          role         TEXT CHECK(role IN ('self','partner','guest')) DEFAULT 'self',
          created_at   DATETIME DEFAULT CURRENT_TIMESTAMP
        );

        -- Focus sessions (legacy / unused but preserved)
        CREATE TABLE IF NOT EXISTS focus_sessions (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          user_id INTEGER,
          started_at_utc DATETIME,
          duration_min INTEGER,
          tag TEXT,
          phone_commit INTEGER,
          phone_free INTEGER,
          completed INTEGER,
          notes TEXT,
          created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );

        CREATE INDEX IF NOT EXISTS idx_focus_user_started
        ON focus_sessions(user_id, started_at_utc);

        -- Daily focus counters
        CREATE TABLE IF NOT EXISTS focus_daily (
          user_id INTEGER,
          local_date DATE,
          sessions INTEGER DEFAULT 0,
          phone_free_sessions INTEGER DEFAULT 0,
          PRIMARY KEY (user_id, local_date)
        );

        -- Focus streaks
        CREATE TABLE IF NOT EXISTS focus_streaks (
          user_id INTEGER PRIMARY KEY,
          target_per_day INTEGER DEFAULT 1,
          last_date DATE,
          streak_days INTEGER DEFAULT 0
        );

        -- Reflection artifacts (NEW, append-only)
        CREATE TABLE IF NOT EXISTS reflection_artifacts (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          timestamp TEXT NOT NULL,
          type TEXT NOT NULL,
          payload_id TEXT NOT NULL,
          recipient TEXT NOT NULL,
          ack TEXT
        );
        """)
