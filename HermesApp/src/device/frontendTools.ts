/**
 * Frontend tools the app declares on every run.
 *
 * Pure-UI tools (show_*) render generative cards inline in the chat; device
 * duplicates are NOT declared here — the backend owns device tools and the
 * app executes them from the TOOL_CALL stream / device queue.
 */
import type { AgTool } from '../agui/types';

const obj = (properties: Record<string, unknown>, required: string[] = []) => ({
  type: 'object' as const,
  properties,
  required,
});

export const FRONTEND_TOOLS: AgTool[] = [
  {
    name: 'show_plan_card',
    description:
      'Render a plan/checklist card inline in the chat UI. Use when presenting a multi-step plan.',
    parameters: obj(
      {
        title: { type: 'string' },
        steps: {
          type: 'array',
          items: obj(
            {
              text: { type: 'string' },
              status: { type: 'string', enum: ['pending', 'in_progress', 'done'] },
            },
            ['text'],
          ),
        },
      },
      ['title', 'steps'],
    ) as AgTool['parameters'],
  },
  {
    name: 'show_media_card',
    description:
      'Render a media card (e.g. a YouTube video about to play) with title, subtitle and optional link.',
    parameters: obj(
      {
        title: { type: 'string' },
        subtitle: { type: 'string' },
        url: { type: 'string' },
      },
      ['title'],
    ) as AgTool['parameters'],
  },
  {
    name: 'show_event_card',
    description: 'Render a calendar-event card (title, start, end, location).',
    parameters: obj(
      {
        title: { type: 'string' },
        start: { type: 'string' },
        end: { type: 'string' },
        location: { type: 'string' },
      },
      ['title', 'start'],
    ) as AgTool['parameters'],
  },
  {
    name: 'show_email_draft',
    description: 'Render an email draft card for review before sending.',
    parameters: obj(
      {
        to: { type: 'string' },
        subject: { type: 'string' },
        body: { type: 'string' },
      },
      ['to', 'subject', 'body'],
    ) as AgTool['parameters'],
  },
  {
    name: 'show_chart',
    description:
      'Render a small bar chart card inline. bars = [{label, value}]. Use for quick comparisons.',
    parameters: obj(
      {
        title: { type: 'string' },
        bars: {
          type: 'array',
          items: obj({ label: { type: 'string' }, value: { type: 'number' } }, ['label', 'value']),
        },
      },
      ['title', 'bars'],
    ) as AgTool['parameters'],
  },
];

/** Friendly labels for tool-activity chips ("Searching the web…"). */
export const TOOL_LABELS: Record<string, string> = {
  search_web: 'Searching the web',
  fetch_web_page: 'Reading a page',
  list_gmail_messages: 'Checking Gmail',
  read_gmail_message: 'Reading an email',
  send_gmail: 'Sending email',
  draft_gmail_reply: 'Replying to email',
  list_apple_mail_messages: 'Checking Apple Mail',
  send_apple_mail: 'Sending email',
  list_calendar_events: 'Checking your calendar',
  create_calendar_event: 'Adding to calendar',
  delete_calendar_event: 'Updating calendar',
  find_free_time_slots: 'Finding free time',
  send_whatsapp_message: 'Sending WhatsApp',
  search_youtube_videos: 'Searching YouTube',
  play_youtube_video: 'Starting playback',
  play_youtube_search: 'Starting playback',
  open_iphone_app: 'Opening app',
  run_iphone_shortcut: 'Running shortcut',
  create_iphone_reminder: 'Adding reminder',
  show_on_iphone_map: 'Opening Maps',
  manage_memory_file: 'Updating memory',
  remember_fact: 'Remembering',
  recall_memories: 'Recalling',
  session_search: 'Searching past chats',
  create_artifact: 'Creating artifact',
  update_artifact: 'Updating artifact',
  create_routine: 'Creating routine',
  list_routines: 'Checking routines',
  write_todos: 'Planning',
  task: 'Delegating research',
};

export function toolLabel(name: string): string {
  return TOOL_LABELS[name] ?? name.replace(/_/g, ' ');
}
