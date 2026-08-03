"""APNs push notifications — routine results and device-command doorbells.

Token-based (.p8) authentication over HTTP/2. Device tokens are registered
by the iPhone app via POST /device/register and stored in Postgres.
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any

import httpx
import jwt

from .. import db
from ..config import settings

logger = logging.getLogger(__name__)


def register_device_token(token: str) -> None:
    db.execute(
        "INSERT INTO hermes.device_tokens (token) VALUES (%s) ON CONFLICT DO NOTHING",
        (token,),
    )


def _device_tokens() -> list[str]:
    return [row["token"] for row in db.query("SELECT token FROM hermes.device_tokens")]


class ApnsClient:
    """Minimal APNs HTTP/2 client with cached provider JWTs."""

    def __init__(self) -> None:
        self._jwt: str | None = None
        self._jwt_issued_at = 0.0

    @property
    def configured(self) -> bool:
        return bool(
            settings.apns_key_id
            and settings.apns_team_id
            and settings.apns_key_path.exists()
        )

    def _provider_token(self) -> str:
        if self._jwt is None or time.time() - self._jwt_issued_at > 2400:  # 40 min
            self._jwt = jwt.encode(
                {"iss": settings.apns_team_id, "iat": int(time.time())},
                settings.apns_key_path.read_text(),
                algorithm="ES256",
                headers={"kid": settings.apns_key_id},
            )
            self._jwt_issued_at = time.time()
        return self._jwt

    def send(self, title: str, body: str, payload: dict[str, Any] | None = None) -> int:
        """Send an alert push to every registered device. Returns delivery count."""
        if not self.configured:
            logger.info("APNs not configured — skipping push: %s", title)
            return 0
        host = (
            "https://api.sandbox.push.apple.com"
            if settings.apns_use_sandbox
            else "https://api.push.apple.com"
        )
        message = {
            "aps": {
                "alert": {"title": title, "body": body},
                "sound": "default",
                "interruption-level": "time-sensitive",
            },
            **(payload or {}),
        }
        delivered = 0
        with httpx.Client(http2=True, timeout=10) as client:
            for token in _device_tokens():
                response = client.post(
                    f"{host}/3/device/{token}",
                    headers={
                        "authorization": f"bearer {self._provider_token()}",
                        "apns-topic": settings.apns_bundle_id,
                        "apns-push-type": "alert",
                    },
                    content=json.dumps(message),
                )
                if response.status_code == 200:
                    delivered += 1
                else:
                    logger.warning(
                        "APNs %s for token %s…: %s",
                        response.status_code, token[:8], response.text,
                    )
        return delivered


apns = ApnsClient()


def send_doorbell(command: str, payload: dict[str, Any]) -> None:
    """Doorbell push: wakes the iOS 26 notification automation → AI: Poll."""
    subject = payload.get("title") or payload.get("query") or payload.get("name") or ""
    apns.send(
        title="Hermes",
        body=f"Action ready: {command.replace('_', ' ')} {subject}".strip(),
        payload={"type": "device_poll"},
    )


_DAILY_PUSH_BUDGET = 4  # proactive interruptions per day; overflow → ledger only


def _budget_available(kind: str) -> bool:
    """Doorbells are user-initiated (exempt); routine pushes spend budget."""
    if kind == "device_poll":
        return True
    rows = db.query(
        "SELECT count(*) AS n FROM hermes.push_log "
        "WHERE kind='routine_result' AND sent_at > now() - interval '24 hours'"
    )
    return (rows[0]["n"] if rows else 0) < _DAILY_PUSH_BUDGET


def send_routine_result(routine_name: str, summary: str) -> None:
    if not _budget_available("routine_result"):
        logger.info("Push budget spent — %s lands in the ledger silently.", routine_name)
        return  # the routine's receipt still appears in the ledger
    db.execute("INSERT INTO hermes.push_log (kind) VALUES ('routine_result')")
    apns.send(
        title=routine_name,
        body=summary[:180],
        payload={"type": "routine_result", "routine": routine_name},
    )
