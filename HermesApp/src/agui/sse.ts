/**
 * Incremental Server-Sent-Events parser.
 *
 * Feed it raw text chunks; it emits the JSON payload of every complete
 * `data: {...}` event. Handles \n\n and \r\n\r\n separators, multi-line data
 * fields, comment lines (":") and [DONE] sentinels.
 */

export class SseParser {
  private buffer = '';

  /** Parse a chunk, returning every complete event's data payload. */
  push(chunk: string): string[] {
    this.buffer += chunk;
    const events: string[] = [];

    // Normalize CRLF so we only need to split on \n\n.
    let boundary = this.findBoundary();
    while (boundary !== -1) {
      const rawEvent = this.buffer.slice(0, boundary.index);
      this.buffer = this.buffer.slice(boundary.index + boundary.length);
      const data = SseParser.extractData(rawEvent);
      if (data !== null) events.push(data);
      boundary = this.findBoundary();
    }
    return events;
  }

  private findBoundary(): { index: number; length: number } | -1 {
    const lf = this.buffer.indexOf('\n\n');
    const crlf = this.buffer.indexOf('\r\n\r\n');
    if (lf === -1 && crlf === -1) return -1;
    if (crlf !== -1 && (lf === -1 || crlf < lf)) return { index: crlf, length: 4 };
    return { index: lf, length: 2 };
  }

  private static extractData(rawEvent: string): string | null {
    const lines = rawEvent.split(/\r?\n/);
    const dataLines: string[] = [];
    for (const line of lines) {
      if (line.startsWith('data:')) {
        // Per spec a single leading space after the colon is stripped.
        dataLines.push(line.slice(5).replace(/^ /, ''));
      }
    }
    if (dataLines.length === 0) return null;
    const data = dataLines.join('\n');
    if (data === '[DONE]') return null;
    return data;
  }
}

/**
 * UTF-8 decode with a manual fallback: Hermes/RN environments do not always
 * expose TextDecoder.
 */
export function createUtf8Decoder(): (bytes: Uint8Array) => string {
  if (typeof TextDecoder !== 'undefined') {
    const decoder = new TextDecoder('utf-8');
    return (bytes) => decoder.decode(bytes, { stream: true });
  }
  // Streaming-safe manual decoder: carries incomplete trailing sequences over.
  let pending: number[] = [];
  return (bytes) => {
    const buf = [...pending, ...Array.from(bytes)];
    pending = [];
    let out = '';
    let i = 0;
    while (i < buf.length) {
      const b0 = buf[i] as number;
      let needed = 0;
      let codePoint = 0;
      if (b0 < 0x80) {
        codePoint = b0;
      } else if ((b0 & 0xe0) === 0xc0) {
        needed = 1;
        codePoint = b0 & 0x1f;
      } else if ((b0 & 0xf0) === 0xe0) {
        needed = 2;
        codePoint = b0 & 0x0f;
      } else if ((b0 & 0xf8) === 0xf0) {
        needed = 3;
        codePoint = b0 & 0x07;
      } else {
        i += 1; // Invalid lead byte; skip.
        continue;
      }
      if (i + needed >= buf.length) {
        // Incomplete multi-byte sequence at the end — stash for the next chunk.
        pending = buf.slice(i);
        break;
      }
      for (let j = 1; j <= needed; j++) {
        codePoint = (codePoint << 6) | ((buf[i + j] as number) & 0x3f);
      }
      out += String.fromCodePoint(codePoint);
      i += needed + 1;
    }
    return out;
  };
}
