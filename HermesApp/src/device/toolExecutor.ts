/**
 * Executes device commands on the phone: deep links, Apple Shortcuts
 * (x-callback for results), reminders/calendar via EventKit.
 * Fed by two sources: TOOL_CALL events on live runs and the backend device
 * queue (push doorbell → poll).
 */
import * as Calendar from 'expo-calendar';
import * as Linking from 'expo-linking';

import { api } from '../api/rest';

const APP_SCHEMES: Record<string, string> = {
  youtube: 'youtube://',
  spotify: 'spotify://',
  whatsapp: 'whatsapp://',
  maps: 'maps://',
  mail: 'message://',
  safari: 'https://www.google.com',
  phone: 'tel:',
  messages: 'sms:',
  camera: 'camera://',
  photos: 'photos-redirect://',
  notes: 'mobilenotes://',
  calendar: 'calshow://',
};

async function openFirst(urls: string[]): Promise<string> {
  for (const url of urls) {
    try {
      await Linking.openURL(url);
      return `opened ${url}`;
    } catch {
      // try next candidate
    }
  }
  throw new Error(`Could not open any of: ${urls.join(', ')}`);
}

/** Pending x-callback resolutions keyed by shortcut run id. */
const shortcutWaiters = new Map<string, (result: string) => void>();

/** Call once from the root layout to resolve shortcut x-callbacks. */
export function handleIncomingUrl(url: string): void {
  const parsed = Linking.parse(url);
  if (parsed.path?.startsWith('shortcut-')) {
    const outcome =
      parsed.path === 'shortcut-result'
        ? String(parsed.queryParams?.result ?? 'done')
        : `error: ${String(parsed.queryParams?.errorMessage ?? 'cancelled')}`;
    const waiter = shortcutWaiters.get('current');
    if (waiter) {
      shortcutWaiters.delete('current');
      waiter(outcome);
    }
  }
}

async function runShortcut(name: string, input: string): Promise<string> {
  const cb = (path: string) => encodeURIComponent(Linking.createURL(path));
  const url =
    `shortcuts://x-callback-url/run-shortcut?name=${encodeURIComponent(name)}` +
    (input ? `&input=text&text=${encodeURIComponent(input)}` : '') +
    `&x-success=${cb('shortcut-result')}&x-error=${cb('shortcut-error')}&x-cancel=${cb('shortcut-error')}`;

  const result = new Promise<string>((resolve) => {
    shortcutWaiters.set('current', resolve);
    setTimeout(() => {
      if (shortcutWaiters.delete('current')) resolve('no result (timed out)');
    }, 30_000);
  });
  await Linking.openURL(url);
  return result;
}

async function createReminder(title: string, dueIso?: string, notes?: string): Promise<string> {
  const { status } = await Calendar.requestRemindersPermissionsAsync();
  if (status !== 'granted') throw new Error('Reminders permission denied');
  const calendar = await Calendar.getDefaultCalendarAsync?.().catch(() => null);
  const reminderCalendars = await Calendar.getCalendarsAsync(Calendar.EntityTypes.REMINDER);
  const target = reminderCalendars[0] ?? calendar;
  if (!target) throw new Error('No Reminders calendar available');
  await Calendar.createReminderAsync(target.id, {
    title,
    notes,
    dueDate: dueIso ? new Date(dueIso) : undefined,
  });
  return `reminder created: ${title}`;
}

/** Execute one device command; returns a short human-readable result. */
export async function executeDeviceCommand(
  name: string,
  payload: Record<string, unknown>,
): Promise<string> {
  const p = payload as Record<string, string>;
  switch (name) {
    case 'play_youtube_video':
      return openFirst([
        `youtube://watch?v=${p.video_id}`,
        `https://www.youtube.com/watch?v=${p.video_id}`,
      ]);
    case 'play_youtube_search': {
      const q = encodeURIComponent(p.query ?? '');
      return openFirst([
        `youtube://results?search_query=${q}`,
        `https://www.youtube.com/results?search_query=${q}`,
      ]);
    }
    case 'open_app': {
      const scheme = p.deep_link || APP_SCHEMES[p.app ?? ''];
      if (!scheme) throw new Error(`Unknown app "${p.app}"`);
      return openFirst([scheme]);
    }
    case 'run_shortcut':
      return runShortcut(p.name ?? '', p.input ?? '');
    case 'create_reminder':
      return createReminder(p.title ?? 'Reminder', p.due_iso || undefined, p.notes || undefined);
    case 'show_map': {
      const q = encodeURIComponent(p.query ?? '');
      return openFirst([`maps:?q=${q}`, `comgooglemaps://?q=${q}`, `https://maps.apple.com/?q=${q}`]);
    }
    default:
      throw new Error(`Unknown device command "${name}"`);
  }
}

/** Drain the backend device queue (after a doorbell push or on foreground). */
export async function drainDeviceQueue(): Promise<void> {
  for (let i = 0; i < 5; i++) {
    const command = await api.nextCommand().catch(() => null);
    if (!command || !command.id) return;
    try {
      const output = await executeDeviceCommand(command.name ?? '', command.payload ?? {});
      await api.reportCommand(command.id, 'success', output);
    } catch (error) {
      await api.reportCommand(command.id, 'error', String(error)).catch(() => undefined);
    }
  }
}
