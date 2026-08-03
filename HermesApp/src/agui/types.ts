/**
 * AG-UI protocol types (https://ag-ui.com).
 *
 * We hand-roll the client rather than depend on @ag-ui/client: its HttpAgent
 * relies on WHATWG streaming `fetch`, which React Native's built-in fetch does
 * not provide. Expo ships a WinterCG-compliant `expo/fetch` with real
 * ReadableStream response bodies, so a small typed SSE client on top of it is
 * both lighter and more reliable here. The event vocabulary below mirrors
 * @ag-ui/core.
 */

export type Json =
  | string
  | number
  | boolean
  | null
  | Json[]
  | { [key: string]: Json };

export type JsonObject = { [key: string]: Json };

// ---------------------------------------------------------------------------
// Messages (wire format, camelCase)
// ---------------------------------------------------------------------------

export type AgRole = 'user' | 'assistant' | 'tool' | 'system';

export interface AgToolCall {
  id: string;
  type: 'function';
  function: {
    name: string;
    /** JSON-encoded arguments. */
    arguments: string;
  };
}

export interface AgMessage {
  id: string;
  role: AgRole;
  content: string;
  /** Present on assistant messages that invoked tools. */
  toolCalls?: AgToolCall[];
  /** Present on role:"tool" result messages. */
  toolCallId?: string;
}

export interface AgTool {
  name: string;
  description: string;
  /** JSON Schema for the tool arguments. */
  parameters: JsonObject;
}

export interface AgContextItem {
  description: string;
  value: string;
}

export interface RunAgentInput {
  threadId: string;
  runId: string;
  messages: AgMessage[];
  tools: AgTool[];
  context: AgContextItem[];
  state: JsonObject;
  forwardedProps: JsonObject;
}

// ---------------------------------------------------------------------------
// Events
// ---------------------------------------------------------------------------

export type AgEventType =
  | 'RUN_STARTED'
  | 'RUN_FINISHED'
  | 'RUN_ERROR'
  | 'STEP_STARTED'
  | 'STEP_FINISHED'
  | 'TEXT_MESSAGE_START'
  | 'TEXT_MESSAGE_CONTENT'
  | 'TEXT_MESSAGE_END'
  | 'TOOL_CALL_START'
  | 'TOOL_CALL_ARGS'
  | 'TOOL_CALL_END'
  | 'TOOL_CALL_RESULT'
  | 'STATE_SNAPSHOT'
  | 'STATE_DELTA'
  | 'MESSAGES_SNAPSHOT'
  | 'REASONING_START'
  | 'REASONING_CONTENT'
  | 'REASONING_END'
  | 'CUSTOM'
  | 'RAW';

interface BaseEvent {
  type: AgEventType;
  timestamp?: number;
}

export interface RunStartedEvent extends BaseEvent {
  type: 'RUN_STARTED';
  threadId?: string;
  runId?: string;
}

export interface RunFinishedEvent extends BaseEvent {
  type: 'RUN_FINISHED';
  threadId?: string;
  runId?: string;
  result?: Json;
}

export interface RunErrorEvent extends BaseEvent {
  type: 'RUN_ERROR';
  message?: string;
  code?: string;
}

export interface StepStartedEvent extends BaseEvent {
  type: 'STEP_STARTED';
  stepName?: string;
}

export interface StepFinishedEvent extends BaseEvent {
  type: 'STEP_FINISHED';
  stepName?: string;
}

export interface TextMessageStartEvent extends BaseEvent {
  type: 'TEXT_MESSAGE_START';
  messageId: string;
  role?: AgRole;
}

export interface TextMessageContentEvent extends BaseEvent {
  type: 'TEXT_MESSAGE_CONTENT';
  messageId: string;
  delta: string;
}

export interface TextMessageEndEvent extends BaseEvent {
  type: 'TEXT_MESSAGE_END';
  messageId: string;
}

export interface ToolCallStartEvent extends BaseEvent {
  type: 'TOOL_CALL_START';
  toolCallId: string;
  toolCallName: string;
  parentMessageId?: string;
}

export interface ToolCallArgsEvent extends BaseEvent {
  type: 'TOOL_CALL_ARGS';
  toolCallId: string;
  delta: string;
}

export interface ToolCallEndEvent extends BaseEvent {
  type: 'TOOL_CALL_END';
  toolCallId: string;
}

export interface ToolCallResultEvent extends BaseEvent {
  type: 'TOOL_CALL_RESULT';
  toolCallId: string;
  messageId?: string;
  content: string;
  role?: 'tool';
}

export interface StateSnapshotEvent extends BaseEvent {
  type: 'STATE_SNAPSHOT';
  snapshot: JsonObject;
}

/** RFC 6902 JSON Patch operation. */
export interface JsonPatchOp {
  op: 'add' | 'replace' | 'remove' | 'copy' | 'move' | 'test';
  path: string;
  value?: Json;
  from?: string;
}

export interface StateDeltaEvent extends BaseEvent {
  type: 'STATE_DELTA';
  delta: JsonPatchOp[];
}

export interface MessagesSnapshotEvent extends BaseEvent {
  type: 'MESSAGES_SNAPSHOT';
  messages: AgMessage[];
}

export interface ReasoningStartEvent extends BaseEvent {
  type: 'REASONING_START';
  messageId?: string;
}

export interface ReasoningContentEvent extends BaseEvent {
  type: 'REASONING_CONTENT';
  delta: string;
}

export interface ReasoningEndEvent extends BaseEvent {
  type: 'REASONING_END';
}

export interface CustomEvent extends BaseEvent {
  type: 'CUSTOM';
  name: string;
  value: Json;
}

export interface RawEvent extends BaseEvent {
  type: 'RAW';
  event?: Json;
  source?: string;
}

export type AgEvent =
  | RunStartedEvent
  | RunFinishedEvent
  | RunErrorEvent
  | StepStartedEvent
  | StepFinishedEvent
  | TextMessageStartEvent
  | TextMessageContentEvent
  | TextMessageEndEvent
  | ToolCallStartEvent
  | ToolCallArgsEvent
  | ToolCallEndEvent
  | ToolCallResultEvent
  | StateSnapshotEvent
  | StateDeltaEvent
  | MessagesSnapshotEvent
  | ReasoningStartEvent
  | ReasoningContentEvent
  | ReasoningEndEvent
  | CustomEvent
  | RawEvent;

/** Older servers emit THINKING_* aliases for reasoning events. */
const THINKING_ALIASES: Record<string, AgEventType> = {
  THINKING_START: 'REASONING_START',
  THINKING_TEXT_MESSAGE_START: 'REASONING_START',
  THINKING_CONTENT: 'REASONING_CONTENT',
  THINKING_TEXT_MESSAGE_CONTENT: 'REASONING_CONTENT',
  THINKING_END: 'REASONING_END',
  THINKING_TEXT_MESSAGE_END: 'REASONING_END',
};

/** Normalize a raw parsed SSE payload into a typed event (or null if unknown). */
export function normalizeEvent(raw: unknown): AgEvent | null {
  if (typeof raw !== 'object' || raw === null) return null;
  const obj = raw as Record<string, unknown>;
  let type = obj.type;
  if (typeof type !== 'string') return null;
  const alias = THINKING_ALIASES[type];
  if (alias) type = alias;
  return { ...obj, type } as AgEvent;
}
