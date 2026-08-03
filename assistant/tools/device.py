"""iPhone control tools.

Every tool enqueues a device command (assistant/server/device_queue.py).
In live chats the app executes instantly from the TOOL_CALL stream; when the
user is away, the APNs doorbell + iOS 26 notification automation runs the
'AI: Poll' shortcut which executes and reports back. Prefer real service
APIs (Gmail, WhatsApp Cloud, calendar tools) over phone automation whenever
one exists — the phone is for things only the device can do.
"""

from __future__ import annotations

import json

from langchain_core.tools import tool

from ..server import device_queue


def _dispatch(name: str, payload: dict) -> str:
    command_id = device_queue.enqueue(name, payload)
    return json.dumps({"dispatched": True, "command_id": command_id, "command": name})


@tool(parse_docstring=True)
def play_youtube_video(video_id: str, title: str = "") -> str:
    """Open YouTube on the user's iPhone and play a specific video now.

    Get video_id from search_youtube_videos first.

    Args:
        video_id: YouTube video id, e.g. 'dQw4w9WgXcQ'
        title: Video title, shown to the user while it opens

    Returns:
        JSON confirming the command was dispatched to the iPhone
    """
    return _dispatch("play_youtube_video", {"video_id": video_id, "title": title})


@tool(parse_docstring=True)
def play_youtube_search(query: str) -> str:
    """Open YouTube search results on the iPhone and start the top result.

    Use when the user just wants 'play X on YouTube' without caring about
    the exact video, or when video search is unavailable.

    Args:
        query: Search text, e.g. 'daft punk around the world'

    Returns:
        JSON confirming the command was dispatched to the iPhone
    """
    return _dispatch("play_youtube_search", {"query": query})


@tool(parse_docstring=True)
def open_iphone_app(app: str, deep_link: str = "") -> str:
    """Open an app on the user's iPhone, optionally at a deep link.

    Supported app names: youtube, spotify, whatsapp, maps, mail, safari,
    phone, messages, camera, photos, notes, calendar. For anything else,
    pass a full URL scheme in deep_link.

    Args:
        app: App name from the supported list, or 'custom'
        deep_link: Optional URL scheme, e.g. 'spotify:search:jazz'

    Returns:
        JSON confirming the command was dispatched to the iPhone
    """
    return _dispatch("open_app", {"app": app, "deep_link": deep_link})


@tool(parse_docstring=True)
def run_iphone_shortcut(shortcut_name: str, input_text: str = "") -> str:
    """Run an Apple Shortcut by name on the user's iPhone.

    This is how you act INSIDE other iPhone apps. The assistant shortcut
    pack provides (silent unless noted): 'AI: Send iMessage' ({to, text}),
    'AI: Send Email', 'AI: Set Focus' ({mode, minutes}), 'AI: Timer'
    ({minutes}), 'AI: Home Scene' ({scene}), 'AI: Navigate' ({destination}),
    'AI: Prefill WhatsApp' ({phone, text} — user taps send). Pass structured
    input as JSON text. Any other shortcut in the user's library also works.

    Args:
        shortcut_name: Exact shortcut name, e.g. 'AI: Send iMessage'
        input_text: Input passed to the shortcut (JSON string for pack shortcuts)

    Returns:
        JSON confirming the command was dispatched to the iPhone
    """
    return _dispatch("run_shortcut", {"name": shortcut_name, "input": input_text})


@tool(parse_docstring=True)
def create_iphone_reminder(title: str, due_iso: str = "", notes: str = "") -> str:
    """Create a reminder in the iPhone's native Reminders app.

    Use for personal to-dos ('remind me to call mom at 6'). For real
    meetings prefer create_calendar_event (Google Calendar).

    Args:
        title: Reminder text
        due_iso: Optional due time in ISO format, e.g. '2026-08-04T18:00:00'
        notes: Optional extra notes

    Returns:
        JSON confirming the command was dispatched to the iPhone
    """
    return _dispatch("create_reminder", {"title": title, "due_iso": due_iso, "notes": notes})


@tool(parse_docstring=True)
def show_on_iphone_map(query: str) -> str:
    """Open Maps on the iPhone showing a place or directions query.

    Args:
        query: Place or search, e.g. 'best coffee near me'

    Returns:
        JSON confirming the command was dispatched to the iPhone
    """
    return _dispatch("show_map", {"query": query})


DEVICE_TOOLS = [
    play_youtube_video,
    play_youtube_search,
    open_iphone_app,
    run_iphone_shortcut,
    create_iphone_reminder,
    show_on_iphone_map,
]
