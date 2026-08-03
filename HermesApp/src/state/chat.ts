/**
 * Chat store: drives AG-UI runs and reduces the event stream into view state.
 *
 * Design notes:
 * - Device tools are executed through the backend's device queue (we drain it
 *   on TOOL_CALL_END) so live-chat and headless paths share one execution
 *   path and commands never run twice.
 * - Frontend show_* tools render cards; their results are sent back in an
 *   automatic follow-up run after RUN_FINISHED (AG-UI contract).
 * - interrupt_on approvals surface via LangGraph interrupts; we detect them
 *   in the stream and resume with forwardedProps.command.resume decisions
 *   (HumanInTheLoopMiddleware decision format).
 */
import { create } from 'zustand';

import { runAgent } from '../agui/client';
import { applyPatch } from '../agui/jsonPatch';
import type { AgEvent, AgMessage, JsonObject } from '../agui/types';
import { api } from '../api/rest';
import { FRONTEND_TOOLS } from '../device/frontendTools';
import { drainDeviceQueue } from '../device/toolExecutor';
import { makeId } from '../lib/ids';
import { useSettings } from './settings';

const DEVICE_TOOL_NAMES = new Set([
  'play_youtube_video',
  'play_youtube_search',
  'open_iphone_app',
  'run_iphone_shortcut',
  'create_iphone_reminder',
  'show_on_iphone_map',
]);

const CARD_TOOL_NAMES = new Set(FRONTEND_TOOLS.map((tool) => tool.name));

export interface Card {
  tool: string;
  args: JsonObject;
}

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  text: string;
  reasoning: string;
  cards: Card[];
  streaming: boolean;
}

export interface ToolActivity {
  toolCallId: string;
  name: string;
  args: string;
  done: boolean;
}

export interface ApprovalRequest {
  action: string;
  args: JsonObject;
}

interface ChatState {
  threadId: string;
  messages: ChatMessage[];
  activity: ToolActivity[];
  sharedState: JsonObject;
  running: boolean;
  error: string | null;
  interrupt: ApprovalRequest[] | null;
  send: (text: string) => Promise<void>;
  resolveInterrupt: (decision: 'approve' | 'reject', editedArgs?: JsonObject) => Promise<void>;
  stop: () => void;
  newThread: () => void;
  loadThread: (threadId: string) => Promise<void>;
}

/** Wire-format history for the current thread (what we POST each run). */
let wireMessages: AgMessage[] = [];
let pendingToolResults: AgMessage[] = [];
let abortController: AbortController | null = null;

function contextItems(): { description: string; value: string }[] {
  const settings = useSettings.getState();
  return [
    { description: 'model', value: settings.modelSpec() },
    { description: 'memory_enabled', value: String(settings.memoryEnabled) },
  ];
}

/** Best-effort extraction of HumanInTheLoop action requests from a raw event. */
function extractInterrupt(event: AgEvent): ApprovalRequest[] | null {
  const text = JSON.stringify(event);
  if (!text.includes('__interrupt__')) return null;
  const requests: ApprovalRequest[] = [];
  const walk = (node: unknown): void => {
    if (Array.isArray(node)) {
      node.forEach(walk);
      return;
    }
    if (typeof node !== 'object' || node === null) return;
    const record = node as Record<string, unknown>;
    const actionRequest = (record.action_request ?? record.actionRequest) as
      | Record<string, unknown>
      | undefined;
    if (actionRequest && typeof actionRequest.action === 'string') {
      requests.push({
        action: actionRequest.action,
        args: (actionRequest.args ?? {}) as JsonObject,
      });
      return;
    }
    if (typeof record.action === 'string' && 'args' in record) {
      requests.push({ action: record.action, args: (record.args ?? {}) as JsonObject });
      return;
    }
    Object.values(record).forEach(walk);
  };
  walk(event);
  return requests.length > 0 ? requests : null;
}

export const useChat = create<ChatState>((set, get) => {
  /** Streaming reducer over AG-UI events. */
  function reduce(event: AgEvent): void {
    switch (event.type) {
      case 'TEXT_MESSAGE_START': {
        if (event.role && event.role !== 'assistant') return;
        set((s) => ({
          messages: [
            ...s.messages,
            { id: event.messageId, role: 'assistant', text: '', reasoning: '', cards: [], streaming: true },
          ],
        }));
        wireMessages.push({ id: event.messageId, role: 'assistant', content: '' });
        break;
      }
      case 'TEXT_MESSAGE_CONTENT': {
        set((s) => ({
          messages: s.messages.map((m) =>
            m.id === event.messageId ? { ...m, text: m.text + event.delta } : m,
          ),
        }));
        const wire = wireMessages.find((m) => m.id === event.messageId);
        if (wire) wire.content += event.delta;
        break;
      }
      case 'TEXT_MESSAGE_END':
        set((s) => ({
          messages: s.messages.map((m) => (m.id === event.messageId ? { ...m, streaming: false } : m)),
        }));
        break;

      case 'REASONING_START':
        break;
      case 'REASONING_CONTENT':
        set((s) => {
          const last = s.messages[s.messages.length - 1];
          if (!last || last.role !== 'assistant') {
            const id = makeId('r');
            return {
              messages: [
                ...s.messages,
                { id, role: 'assistant', text: '', reasoning: event.delta, cards: [], streaming: true },
              ],
            };
          }
          return {
            messages: s.messages.map((m, i) =>
              i === s.messages.length - 1 ? { ...m, reasoning: m.reasoning + event.delta } : m,
            ),
          };
        });
        break;
      case 'REASONING_END':
        break;

      case 'TOOL_CALL_START':
        set((s) => ({
          activity: [
            ...s.activity,
            { toolCallId: event.toolCallId, name: event.toolCallName, args: '', done: false },
          ],
        }));
        break;
      case 'TOOL_CALL_ARGS':
        set((s) => ({
          activity: s.activity.map((a) =>
            a.toolCallId === event.toolCallId ? { ...a, args: a.args + event.delta } : a,
          ),
        }));
        break;
      case 'TOOL_CALL_END': {
        const call = get().activity.find((a) => a.toolCallId === event.toolCallId);
        set((s) => ({
          activity: s.activity.map((a) =>
            a.toolCallId === event.toolCallId ? { ...a, done: true } : a,
          ),
        }));
        if (!call) break;

        // Record the tool call on the last assistant wire message.
        const lastAssistant = [...wireMessages].reverse().find((m) => m.role === 'assistant');
        if (lastAssistant) {
          lastAssistant.toolCalls = [
            ...(lastAssistant.toolCalls ?? []),
            { id: call.toolCallId, type: 'function', function: { name: call.name, arguments: call.args } },
          ];
        }

        if (CARD_TOOL_NAMES.has(call.name)) {
          let args: JsonObject = {};
          try {
            args = JSON.parse(call.args || '{}') as JsonObject;
          } catch {
            args = {};
          }
          set((s) => {
            const last = s.messages[s.messages.length - 1];
            if (last?.role === 'assistant') {
              return {
                messages: s.messages.map((m, i) =>
                  i === s.messages.length - 1
                    ? { ...m, cards: [...m.cards, { tool: call.name, args }] }
                    : m,
                ),
              };
            }
            return {
              messages: [
                ...s.messages,
                {
                  id: makeId('c'),
                  role: 'assistant',
                  text: '',
                  reasoning: '',
                  cards: [{ tool: call.name, args }],
                  streaming: false,
                },
              ],
            };
          });
          pendingToolResults.push({
            id: makeId('tr'),
            role: 'tool',
            content: 'shown',
            toolCallId: call.toolCallId,
          });
        } else if (DEVICE_TOOL_NAMES.has(call.name)) {
          // Single execution path: the backend queued the command; claim it now.
          void drainDeviceQueue();
        }
        break;
      }
      case 'TOOL_CALL_RESULT':
        wireMessages.push({
          id: event.messageId ?? makeId('t'),
          role: 'tool',
          content: event.content,
          toolCallId: event.toolCallId,
        });
        break;

      case 'STATE_SNAPSHOT':
        set({ sharedState: event.snapshot });
        break;
      case 'STATE_DELTA':
        set((s) => ({ sharedState: applyPatch(s.sharedState, event.delta) }));
        break;
      case 'MESSAGES_SNAPSHOT':
        wireMessages = event.messages;
        break;

      case 'RUN_ERROR':
        set({ error: event.message ?? 'The agent hit an error.', running: false });
        break;

      case 'RAW':
      case 'CUSTOM': {
        const interrupt = extractInterrupt(event);
        if (interrupt) set({ interrupt });
        break;
      }
      default:
        break;
    }
  }

  async function executeRun(extraForwardedProps: JsonObject = {}): Promise<void> {
    const { serverUrl, authToken } = useSettings.getState();
    abortController = new AbortController();
    set({ running: true, error: null, activity: [] });
    try {
      await runAgent({
        serverUrl,
        authToken,
        input: {
          threadId: get().threadId,
          runId: makeId('run'),
          messages: [...wireMessages],
          tools: FRONTEND_TOOLS,
          context: contextItems(),
          state: get().sharedState,
          forwardedProps: extraForwardedProps,
        },
        onEvent: reduce,
        signal: abortController.signal,
      });
    } catch (error) {
      if ((error as Error).name !== 'AbortError') set({ error: String((error as Error).message) });
    } finally {
      set((s) => ({
        running: false,
        messages: s.messages.map((m) => ({ ...m, streaming: false })),
      }));
      // Frontend tool results trigger one automatic continuation run.
      if (pendingToolResults.length > 0 && !get().interrupt) {
        wireMessages.push(...pendingToolResults);
        pendingToolResults = [];
        await executeRun();
      }
    }
  }

  return {
    threadId: makeId('thread-'),
    messages: [],
    activity: [],
    sharedState: {},
    running: false,
    error: null,
    interrupt: null,

    send: async (text: string) => {
      if (get().running) return;
      const id = makeId('u');
      wireMessages.push({ id, role: 'user', content: text });
      set((s) => ({
        messages: [
          ...s.messages,
          { id, role: 'user', text, reasoning: '', cards: [], streaming: false },
        ],
      }));
      await executeRun();
    },

    resolveInterrupt: async (decision, editedArgs) => {
      const requests = get().interrupt ?? [];
      set({ interrupt: null });
      const decisions: JsonObject[] = requests.map((): JsonObject => {
        if (decision !== 'approve') return { type: 'reject' };
        return editedArgs ? { type: 'edit', args: editedArgs } : { type: 'approve' };
      });
      await executeRun({ command: { resume: decisions } });
    },

    stop: () => {
      abortController?.abort();
      set({ running: false });
    },

    newThread: () => {
      abortController?.abort();
      wireMessages = [];
      pendingToolResults = [];
      set({
        threadId: makeId('thread-'),
        messages: [],
        activity: [],
        sharedState: {},
        running: false,
        error: null,
        interrupt: null,
      });
    },

    loadThread: async (threadId: string) => {
      abortController?.abort();
      const logged = await api.threadMessages(threadId);
      wireMessages = [];
      pendingToolResults = [];
      const messages: ChatMessage[] = [];
      for (const entry of logged) {
        if (entry.role !== 'human' && entry.role !== 'ai') continue;
        const role = entry.role === 'human' ? 'user' : 'assistant';
        const id = makeId(role[0] ?? 'm');
        wireMessages.push({ id, role: role === 'user' ? 'user' : 'assistant', content: entry.content });
        messages.push({ id, role, text: entry.content, reasoning: '', cards: [], streaming: false });
      }
      set({
        threadId,
        messages,
        activity: [],
        sharedState: {},
        running: false,
        error: null,
        interrupt: null,
      });
    },
  };
});
