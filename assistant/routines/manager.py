"""Routine engine — proactive scheduled agent runs (Hermes cron pattern).

A routine = cron schedule + natural-language prompt. Each fire runs the
prompt in a FRESH thread (no chat history), with the routine tools disabled
inside the run (recursion guard). Results are delivered as a push
notification and recorded on the routine — never mirrored into chat threads.
Storage: Postgres. Scheduling: APScheduler.
"""

from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass
from typing import Awaitable, Callable

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from .. import db
from ..config import settings

logger = logging.getLogger(__name__)

RunCallback = Callable[["Routine"], Awaitable[str]]


@dataclass
class Routine:
    id: str
    name: str
    cron: str
    prompt: str
    enabled: bool = True

    @staticmethod
    def from_row(row: dict) -> "Routine":
        return Routine(
            id=row["id"], name=row["name"], cron=row["cron"],
            prompt=row["prompt"], enabled=row["enabled"],
        )


class RoutineManager:
    def __init__(self) -> None:
        self._scheduler = AsyncIOScheduler(timezone=settings.timezone)
        self._runner: RunCallback | None = None

    # --- lifecycle ---

    def start(self, runner: RunCallback) -> None:
        self._runner = runner
        self._scheduler.start()
        for routine in self.list():
            if routine.enabled:
                self._schedule(routine)
        logger.info("Routine scheduler started with %d routines.", len(self.list()))

    def shutdown(self) -> None:
        if self._scheduler.running:
            self._scheduler.shutdown(wait=False)

    # --- CRUD ---

    def create(self, name: str, cron: str, prompt: str) -> Routine:
        CronTrigger.from_crontab(cron, timezone=settings.timezone)  # validate early
        routine = Routine(id=uuid.uuid4().hex[:12], name=name, cron=cron, prompt=prompt)
        db.execute(
            "INSERT INTO hermes.routines (id, name, cron, prompt) VALUES (%s,%s,%s,%s)",
            (routine.id, name, cron, prompt),
        )
        if self._scheduler.running:
            self._schedule(routine)
        return routine

    def list(self) -> list[Routine]:
        return [Routine.from_row(r) for r in
                db.query("SELECT * FROM hermes.routines ORDER BY created_at")]

    def list_full(self) -> list[dict]:
        rows = db.query(
            "SELECT id, name, cron, prompt, enabled, created_at::text, "
            "last_run_at::text, last_result FROM hermes.routines ORDER BY created_at"
        )
        return list(rows)

    def set_enabled(self, routine_id: str, enabled: bool) -> bool:
        changed = db.execute(
            "UPDATE hermes.routines SET enabled=%s WHERE id=%s", (enabled, routine_id)
        )
        if not changed:
            return False
        self._unschedule(routine_id)
        if enabled and self._scheduler.running:
            rows = db.query("SELECT * FROM hermes.routines WHERE id=%s", (routine_id,))
            self._schedule(Routine.from_row(rows[0]))
        return True

    def delete(self, routine_id: str) -> bool:
        self._unschedule(routine_id)
        return db.execute("DELETE FROM hermes.routines WHERE id=%s", (routine_id,)) > 0

    def to_json(self) -> str:
        return json.dumps(self.list_full(), default=str)

    # --- execution ---

    async def _fire(self, routine: Routine) -> None:
        if not self._runner:
            return
        logger.info("Routine %s firing.", routine.name)
        try:
            result = await self._runner(routine)
        except Exception as exc:
            logger.exception("Routine %s failed.", routine.name)
            result = f"Routine failed: {exc}"
        db.execute(
            "UPDATE hermes.routines SET last_run_at=now(), last_result=%s WHERE id=%s",
            (result[:2000], routine.id),
        )
        from ..server.push import send_routine_result

        send_routine_result(routine.name, result)

    def _schedule(self, routine: Routine) -> None:
        self._scheduler.add_job(
            self._fire,
            CronTrigger.from_crontab(routine.cron, timezone=settings.timezone),
            args=[routine],
            id=routine.id,
            replace_existing=True,
            misfire_grace_time=300,
        )

    def _unschedule(self, routine_id: str) -> None:
        if self._scheduler.get_job(routine_id):
            self._scheduler.remove_job(routine_id)


routine_manager = RoutineManager()
