/**
 * AG-UI client over expo/fetch (WinterCG fetch with streaming bodies).
 * POSTs a RunAgentInput and yields typed events via callback until the
 * stream closes, errors, or the caller aborts.
 */
import { fetch as expoFetch } from 'expo/fetch';

import { SseParser, createUtf8Decoder } from './sse';
import { normalizeEvent, type AgEvent, type RunAgentInput } from './types';

export interface RunOptions {
  serverUrl: string;
  authToken: string;
  input: RunAgentInput;
  onEvent: (event: AgEvent) => void;
  signal?: AbortSignal;
}

export async function runAgent({ serverUrl, authToken, input, onEvent, signal }: RunOptions): Promise<void> {
  const response = await expoFetch(`${serverUrl.replace(/\/$/, '')}/agent`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Accept: 'text/event-stream',
      Authorization: `Bearer ${authToken}`,
    },
    body: JSON.stringify(input),
    signal,
  });

  if (!response.ok || !response.body) {
    const detail = await response.text().catch(() => '');
    throw new Error(`Agent request failed (${response.status}): ${detail.slice(0, 300)}`);
  }

  const reader = response.body.getReader();
  const decode = createUtf8Decoder();
  const parser = new SseParser();

  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    if (!value) continue;
    for (const payload of parser.push(decode(value))) {
      try {
        const event = normalizeEvent(JSON.parse(payload));
        if (event) onEvent(event);
      } catch {
        // Malformed frame — skip rather than kill the stream.
      }
    }
  }
}
