"""Google Calendar tools — list, create, delete events and find free slots."""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from langchain_core.tools import tool

from ..config import settings
from ..google_auth import calendar_service


def _tz() -> ZoneInfo:
    return ZoneInfo(settings.timezone)


def _iso(dt: datetime) -> str:
    return dt.isoformat()


@tool(parse_docstring=True, handle_tool_error=True)
def list_calendar_events(days_ahead: int = 7, max_results: int = 20) -> str:
    """List upcoming Google Calendar events for the next N days.

    Args:
        days_ahead: How many days into the future to look (1-60)
        max_results: Maximum number of events to return

    Returns:
        JSON list of {id, summary, start, end, location}
    """
    now = datetime.now(_tz())
    service = calendar_service()
    result = (
        service.events()
        .list(
            calendarId="primary",
            timeMin=_iso(now),
            timeMax=_iso(now + timedelta(days=min(max(days_ahead, 1), 60))),
            singleEvents=True,
            orderBy="startTime",
            maxResults=max_results,
        )
        .execute()
    )
    events = [
        {
            "id": e["id"],
            "summary": e.get("summary", "(no title)"),
            "start": e["start"].get("dateTime", e["start"].get("date")),
            "end": e["end"].get("dateTime", e["end"].get("date")),
            "location": e.get("location", ""),
        }
        for e in result.get("items", [])
    ]
    return json.dumps(events)


@tool(parse_docstring=True, handle_tool_error=True)
def create_calendar_event(
    summary: str,
    start_iso: str,
    end_iso: str,
    description: str = "",
    location: str = "",
) -> str:
    """Create a Google Calendar event on the user's primary calendar.

    Args:
        summary: Event title
        start_iso: Start time in ISO format, e.g. '2026-08-04T15:00:00'
        end_iso: End time in ISO format, e.g. '2026-08-04T16:00:00'
        description: Optional longer description
        location: Optional location string

    Returns:
        JSON {created: true, id, htmlLink}
    """
    event = {
        "summary": summary,
        "description": description,
        "location": location,
        "start": {"dateTime": start_iso, "timeZone": settings.timezone},
        "end": {"dateTime": end_iso, "timeZone": settings.timezone},
    }
    created = calendar_service().events().insert(calendarId="primary", body=event).execute()
    return json.dumps({"created": True, "id": created["id"], "htmlLink": created.get("htmlLink")})


@tool(parse_docstring=True, handle_tool_error=True)
def delete_calendar_event(event_id: str) -> str:
    """Delete an event from the user's primary Google Calendar by id.

    Args:
        event_id: Event id from list_calendar_events

    Returns:
        JSON {deleted: true}
    """
    calendar_service().events().delete(calendarId="primary", eventId=event_id).execute()
    return json.dumps({"deleted": True})


@tool(parse_docstring=True, handle_tool_error=True)
def find_free_time_slots(
    date: str,
    duration_minutes: int = 60,
    day_start_hour: int = 9,
    day_end_hour: int = 21,
) -> str:
    """Find free time slots of a given duration on a specific date.

    Checks the user's primary Google Calendar between working hours and
    returns gaps large enough for the requested duration.

    Args:
        date: Date to check, format 'YYYY-MM-DD'
        duration_minutes: Minimum slot length needed, in minutes
        day_start_hour: Earliest hour to consider (24h clock)
        day_end_hour: Latest hour to consider (24h clock)

    Returns:
        JSON list of {start, end} free slots in local time
    """
    tz = _tz()
    day = datetime.fromisoformat(date).replace(tzinfo=tz)
    window_start = day.replace(hour=day_start_hour, minute=0, second=0, microsecond=0)
    window_end = day.replace(hour=day_end_hour, minute=0, second=0, microsecond=0)

    result = (
        calendar_service()
        .freebusy()
        .query(
            body={
                "timeMin": _iso(window_start),
                "timeMax": _iso(window_end),
                "items": [{"id": "primary"}],
            }
        )
        .execute()
    )
    busy = [
        (datetime.fromisoformat(b["start"]), datetime.fromisoformat(b["end"]))
        for b in result["calendars"]["primary"]["busy"]
    ]

    slots, cursor = [], window_start
    needed = timedelta(minutes=duration_minutes)
    for busy_start, busy_end in sorted(busy):
        if busy_start - cursor >= needed:
            slots.append({"start": _iso(cursor), "end": _iso(busy_start)})
        cursor = max(cursor, busy_end)
    if window_end - cursor >= needed:
        slots.append({"start": _iso(cursor), "end": _iso(window_end)})
    return json.dumps(slots)
