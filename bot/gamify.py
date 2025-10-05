# bot/gamify.py
import sqlite3
import os
from datetime import datetime, date, timedelta
from typing import Optional, Dict, List, Tuple

# DB path: use V30X_DATA_DIR (same pattern as other modules)
V30X_DATA_DIR = os.getenv("V30X_DATA_DIR", str((__import__("pathlib").Path.home() / ".vison30x")))
os.makedirs(V30X_DATA_DIR, exist_ok=True)
DB_PATH = os.path.join(V30X_DATA_DIR, "vision30x.db")

def _conn():
    return sqlite3.connect(DB_PATH, detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES)

def init_gamify_tables():
    sql = [
        """
        CREATE TABLE IF NOT EXISTS gamify_users (
            user_id INTEGER PRIMARY KEY,
            chat_id INTEGER,
            display_name TEXT,
            xp INTEGER DEFAULT 0,
            level INTEGER DEFAULT 1,
            created_at TEXT DEFAULT (datetime('now'))
        )""",
        """
        CREATE TABLE IF NOT EXISTS pomodoros (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            start_ts TEXT,
            end_ts TEXT,
            duration_min INTEGER,
            phone_free INTEGER DEFAULT 0,
            tag TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        )""",
        """
        CREATE TABLE IF NOT EXISTS calls (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            start_ts TEXT,
            end_ts TEXT,
            duration_min INTEGER,
            tag TEXT,
            notes TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        )""",
        """
        CREATE TABLE IF NOT EXISTS badges (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            key TEXT NOT NULL,
            label TEXT,
            awarded_at TEXT DEFAULT (datetime('now'))
        )"""
    ]
    with _conn() as conn:
        cur = conn.cursor()
        for s in sql:
            cur.execute(s)
        conn.commit()

# --- user registration ---
def register_user(user_id:int, chat_id:Optional[int]=None, display_name:Optional[str]=None):
    with _conn() as conn:
        cur = conn.cursor()
        cur.execute("INSERT OR IGNORE INTO gamify_users(user_id, chat_id, display_name) VALUES (?, ?, ?)",
                    (user_id, chat_id, display_name))
        # if user exists but chat_id/display_name missing, update
        cur.execute("UPDATE gamify_users SET chat_id = COALESCE(?, chat_id), display_name = COALESCE(?, display_name) WHERE user_id = ?",
                    (chat_id, display_name, user_id))
        conn.commit()

# --- xp / level helpers ---
def _level_from_xp(xp:int)->int:
    # simple rule: every 500 XP -> +1 level (tweakable)
    return xp // 500 + 1

def add_xp(user_id:int, xp:int) -> Tuple[int,int]:
    """Add xp; return (old_level, new_level)"""
    with _conn() as conn:
        cur = conn.cursor()
        cur.execute("SELECT xp, level FROM gamify_users WHERE user_id=?", (user_id,))
        row = cur.fetchone()
        if not row:
            cur.execute("INSERT INTO gamify_users(user_id, xp, level) VALUES (?, ?, ?)",
                        (user_id, xp, _level_from_xp(xp)))
            conn.commit()
            return (1, _level_from_xp(xp))
        old_xp, old_level = row
        new_xp = old_xp + xp
        new_level = _level_from_xp(new_xp)
        cur.execute("UPDATE gamify_users SET xp=?, level=? WHERE user_id=?", (new_xp, new_level, user_id))
        conn.commit()
        return old_level, new_level

# --- pomodoro recording ---
def record_pomodoro(user_id:int, start_ts:str, end_ts:str, duration_min:int, phone_free:bool=False, tag:Optional[str]=None):
    with _conn() as conn:
        cur = conn.cursor()
        cur.execute("""INSERT INTO pomodoros(user_id,start_ts,end_ts,duration_min,phone_free,tag)
                       VALUES (?,?,?,?,?,?)""",
                    (user_id, start_ts, end_ts, duration_min, int(phone_free), tag))
        xp = 10 + (5 if phone_free else 0)
        add_xp(user_id, xp)
        conn.commit()

# --- calls logging ---
def log_call(user_id:int, minutes:int, tag:Optional[str]=None, notes:Optional[str]=None, start_ts:Optional[str]=None, end_ts:Optional[str]=None):
    if not end_ts:
        end_ts = datetime.utcnow().isoformat()
    if not start_ts:
        start_ts = (datetime.utcnow() - timedelta(minutes=minutes)).isoformat()
    with _conn() as conn:
        cur = conn.cursor()
        cur.execute("""INSERT INTO calls(user_id,start_ts,end_ts,duration_min,tag,notes)
                       VALUES (?,?,?,?,?,?)""",
                    (user_id, start_ts, end_ts, minutes, tag, notes))
        xp = 15 if minutes >= 10 else 5
        add_xp(user_id, xp)
        conn.commit()

# --- in-memory call sessions (start_call / end_call) ---
# NOTE: simple in-memory store; restarts will lose sessions but DB logs remain available via /log_call
_incall_sessions = {}  # user_id -> {"start_ts": iso, "tag":..., "notes":...}

def start_call_session(user_id:int, tag:Optional[str]=None, notes:Optional[str]=None):
    if user_id in _incall_sessions:
        return False  # already started
    _incall_sessions[user_id] = {"start_ts": datetime.utcnow().isoformat(), "tag": tag, "notes": notes}
    return True

def end_call_session(user_id:int) -> Optional[Dict]:
    sess = _incall_sessions.pop(user_id, None)
    if not sess:
        return None
    start = datetime.fromisoformat(sess["start_ts"])
    end = datetime.utcnow()
    minutes = int((end - start).total_seconds() // 60)
    log_call(user_id, minutes, tag=sess.get("tag"), notes=sess.get("notes"), start_ts=sess["start_ts"], end_ts=end.isoformat())
    return {"minutes": minutes, "start_ts": sess["start_ts"], "end_ts": end.isoformat()}

# --- weekly summary utilities ---
def _week_range_for(date_obj:date=None)->Tuple[str,str]:
    if date_obj is None:
        date_obj = date.today()
    start = date_obj - timedelta(days=date_obj.weekday())  # monday
    end = start + timedelta(days=6)
    return start.isoformat(), end.isoformat()

def get_weekly_summary(user_id:int, ref_date:date=None)->Dict:
    start_iso, end_iso = _week_range_for(ref_date)
    with _conn() as conn:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*), COALESCE(SUM(duration_min),0) FROM pomodoros WHERE user_id=? AND date(created_at) BETWEEN ? AND ?",
                    (user_id, start_iso, end_iso))
        pom_count, pom_minutes = cur.fetchone()
        cur.execute("SELECT COUNT(*), COALESCE(SUM(duration_min),0) FROM calls WHERE user_id=? AND date(created_at) BETWEEN ? AND ?",
                    (user_id, start_iso, end_iso))
        call_count, call_minutes = cur.fetchone()
        cur.execute("SELECT xp, level FROM gamify_users WHERE user_id=?", (user_id,))
        xp_row = cur.fetchone()
        xp = xp_row[0] if xp_row else 0
        level = xp_row[1] if xp_row else 1
        cur.execute("SELECT key,label,awarded_at FROM badges WHERE user_id=? AND date(awarded_at) BETWEEN ? AND ?",
                    (user_id, start_iso, end_iso))
        badges = cur.fetchall()
    return {
        "week_start": start_iso,
        "week_end": end_iso,
        "pomodoros": int(pom_count or 0),
        "pom_minutes": int(pom_minutes or 0),
        "calls": int(call_count or 0),
        "call_minutes": int(call_minutes or 0),
        "xp": int(xp or 0),
        "level": int(level or 1),
        "badges": [{"key":b[0],"label":b[1],"awarded_at":b[2]} for b in badges]
    }

# --- badges ---
def award_badge(user_id:int, key:str, label:str) -> bool:
    with _conn() as conn:
        cur = conn.cursor()
        cur.execute("SELECT 1 FROM badges WHERE user_id=? AND key=?", (user_id, key))
        if cur.fetchone():
            return False
        cur.execute("INSERT INTO badges(user_id,key,label) VALUES (?,?,?)", (user_id, key, label))
        conn.commit()
        return True

# --- leaderboard (by pomodoros) ---
def leaderboard_by_pomodoros(ref_date:date=None, limit:int=10):
    start_iso, end_iso = _week_range_for(ref_date)
    with _conn() as conn:
        cur = conn.cursor()
        cur.execute("""SELECT user_id, COUNT(*) as cnt
                       FROM pomodoros
                       WHERE date(created_at) BETWEEN ? AND ?
                       GROUP BY user_id
                       ORDER BY cnt DESC
                       LIMIT ?""", (start_iso, end_iso, limit))
        rows = cur.fetchall()
    return [{"user_id": r[0], "pomodoros": r[1]} for r in rows]
