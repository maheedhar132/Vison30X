# bot/reflection.py
import sqlite3
from datetime import datetime
from typing import Literal, Optional
from bot.db import get_conn


ReflectionType = Literal["manifestation", "card"]
RecipientType = Literal["me", "her"]


def record_reflection(
    reflection_type: ReflectionType,
    payload_id: str,
    recipient: RecipientType,
    ack: Optional[str] = None,
):
    """
    Records a reflection artifact.
    This is append-only, no updates.
    """
    ts = datetime.utcnow().isoformat()

    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO reflection_artifacts
            (timestamp, type, payload_id, recipient, ack)
            VALUES (?, ?, ?, ?, ?)
            """,
            (ts, reflection_type, payload_id, recipient, ack),
        )
        conn.commit()
