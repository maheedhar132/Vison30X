# bot/reflection.py
from __future__ import annotations
from datetime import datetime
from typing import Literal, Optional

import bot.db as db

ReflectionType = Literal["manifestation", "card"]
RecipientType = Literal["me", "her"]

def record_reflection(
    reflection_type: ReflectionType,
    payload_id: str,
    recipient: RecipientType,
    ack: Optional[str] = None,
) -> None:
    """
    Append-only reflection artifact.
    """
    ts = datetime.utcnow().isoformat()

    with db.connect() as conn:
        conn.execute(
            """
            INSERT INTO reflection_artifacts
            (timestamp, type, payload_id, recipient, ack)
            VALUES (?, ?, ?, ?, ?)
            """,
            (ts, reflection_type, payload_id, recipient, ack),
        )
