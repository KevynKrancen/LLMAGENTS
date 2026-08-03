"""All backend tools for the Hermes assistant, grouped by domain.

Every tool is a plain ``@tool``-decorated function (langchain-core 1.2+).
Device tools dispatch to the iPhone; see device.py.
"""

from .apple_mail import list_apple_mail_messages, send_apple_mail
from .artifacts import create_artifact, update_artifact
from .calendar import (
    create_calendar_event,
    delete_calendar_event,
    find_free_time_slots,
    list_calendar_events,
)
from .gmail import draft_gmail_reply, list_gmail_messages, read_gmail_message, send_gmail
from .memory import forget_memory, manage_memory_file, recall_memories, remember_fact
from .routines import (
    create_routine,
    delete_routine,
    list_routines,
    pause_or_resume_routine,
)
from .session_search import session_search
from .workspace import save_note, shape_workspace, view_workspace
from .web import fetch_web_page, search_web
from .whatsapp import send_whatsapp_message, send_whatsapp_template
from .youtube import search_youtube_videos

ROUTINE_TOOLS = [create_routine, list_routines, pause_or_resume_routine, delete_routine]

MEMORY_TOOLS = [manage_memory_file, remember_fact, recall_memories, forget_memory]

CORE_TOOLS = [
    # research
    search_web,
    fetch_web_page,
    # email
    list_gmail_messages,
    read_gmail_message,
    send_gmail,
    draft_gmail_reply,
    list_apple_mail_messages,
    send_apple_mail,
    # calendar
    list_calendar_events,
    create_calendar_event,
    delete_calendar_event,
    find_free_time_slots,
    # whatsapp
    send_whatsapp_message,
    send_whatsapp_template,
    # youtube
    search_youtube_videos,
    # memory + recall
    *MEMORY_TOOLS,
    session_search,
    # artifacts + workspace
    create_artifact,
    update_artifact,
    shape_workspace,
    view_workspace,
    save_note,
]

# Full set for interactive chat (routine management included).
BACKEND_TOOLS = [*CORE_TOOLS, *ROUTINE_TOOLS]

# Scoped set for headless routine runs: no routine management inside a
# routine (recursion guard, Hermes pattern).
ROUTINE_RUN_TOOLS = CORE_TOOLS

# Minimal set for untrusted inbound surfaces (WhatsApp webhook): read-mostly,
# no outbound sends, no device control (prompt-injection blast-radius control).
WEBHOOK_TOOLS = [
    search_web,
    fetch_web_page,
    list_calendar_events,
    find_free_time_slots,
    recall_memories,
    session_search,
]

__all__ = [
    "BACKEND_TOOLS",
    "CORE_TOOLS",
    "MEMORY_TOOLS",
    "ROUTINE_RUN_TOOLS",
    "ROUTINE_TOOLS",
    "WEBHOOK_TOOLS",
]
