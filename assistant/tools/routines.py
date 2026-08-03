"""Routine tools — let the agent create and manage proactive schedules."""

from __future__ import annotations

import json

from langchain_core.tools import tool

from ..routines import routine_manager


@tool(parse_docstring=True, handle_tool_error=True)
def create_routine(name: str, cron: str, prompt: str) -> str:
    """Create a recurring routine that runs the assistant proactively.

    When the schedule fires, the assistant executes the prompt headlessly
    and sends the result to the user's iPhone as a push notification.
    Examples: a 7am daily brief, a Friday weekly review, an hourly
    stock check.

    Args:
        name: Short human name, e.g. 'Morning brief'
        cron: Standard 5-field cron in the user's timezone,
            e.g. '0 7 * * *' (daily 7:00) or '30 18 * * 5' (Fri 18:30)
        prompt: The instruction to run each time, e.g. 'Summarize my
            calendar for today, unread important emails, and the weather.'

    Returns:
        JSON of the created routine {id, name, cron, prompt, enabled}
    """
    routine = routine_manager.create(name=name, cron=cron, prompt=prompt)
    return json.dumps(
        {"id": routine.id, "name": routine.name, "cron": routine.cron,
         "prompt": routine.prompt, "enabled": routine.enabled}
    )


@tool(parse_docstring=True, handle_tool_error=True)
def list_routines() -> str:
    """List all routines with their schedules, status, and last run result.

    Returns:
        JSON list of routines {id, name, cron, prompt, enabled, last_run_at, last_result}
    """
    return routine_manager.to_json()


@tool(parse_docstring=True, handle_tool_error=True)
def pause_or_resume_routine(routine_id: str, enabled: bool) -> str:
    """Pause (enabled=false) or resume (enabled=true) a routine by id.

    Args:
        routine_id: Routine id from list_routines
        enabled: True to resume the schedule, False to pause it

    Returns:
        JSON of the updated routine, or an error if the id is unknown
    """
    if not routine_manager.set_enabled(routine_id, enabled):
        return json.dumps({"error": f"No routine with id {routine_id}"})
    return json.dumps({"id": routine_id, "enabled": enabled})


@tool(parse_docstring=True, handle_tool_error=True)
def delete_routine(routine_id: str) -> str:
    """Permanently delete a routine by id. Ask the user before deleting.

    Args:
        routine_id: Routine id from list_routines

    Returns:
        JSON {deleted: true|false}
    """
    return json.dumps({"deleted": routine_manager.delete(routine_id)})
