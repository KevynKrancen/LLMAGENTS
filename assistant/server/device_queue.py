"""Device command queue.

Device tools enqueue commands here. Delivery paths, in order:
1. Live chat: the app also sees the TOOL_CALL stream and can execute
   immediately; it then acknowledges via POST /device/results.
2. Zero-tap: an APNs "doorbell" push triggers the iOS 26 notification
   automation → the 'AI: Poll' shortcut fetches pending commands via
   GET /device/next-command and reports back.
"""

from __future__ import annotations

import json
import uuid

from .. import db


def enqueue(name: str, payload: dict) -> str:
    command_id = uuid.uuid4().hex[:12]
    db.execute(
        "INSERT INTO hermes.device_commands (id, name, payload) VALUES (%s, %s, %s)",
        (command_id, name, json.dumps(payload)),
    )
    from .push import send_doorbell  # local import avoids a cycle at import time

    send_doorbell(name, payload)
    return command_id


def next_pending() -> dict | None:
    rows = db.query(
        """UPDATE hermes.device_commands
           SET status='delivered', updated_at=now()
           WHERE id = (SELECT id FROM hermes.device_commands
                       WHERE status='pending' ORDER BY created_at LIMIT 1)
           RETURNING id, name, payload""",
    )
    return rows[0] if rows else None


def record_result(command_id: str, status: str, output: str) -> bool:
    return (
        db.execute(
            "UPDATE hermes.device_commands SET status=%s, result=%s, updated_at=now() "
            "WHERE id=%s",
            ("done" if status == "success" else "failed", output[:2000], command_id),
        )
        > 0
    )
