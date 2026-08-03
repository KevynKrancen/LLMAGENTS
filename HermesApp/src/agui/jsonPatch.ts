/**
 * Minimal RFC 6902 JSON Patch application: add / replace / remove.
 * (copy/move/test are not emitted by our backend's STATE_DELTA events.)
 *
 * Applies immutably: containers along each touched path are shallow-cloned so
 * zustand/React reference-equality checks see fresh objects.
 */
import type { Json, JsonObject, JsonPatchOp } from './types';

function unescapeToken(token: string): string {
  return token.replace(/~1/g, '/').replace(/~0/g, '~');
}

function parsePath(path: string): string[] {
  if (path === '' || path === '/') return [];
  return path
    .replace(/^\//, '')
    .split('/')
    .map(unescapeToken);
}

function cloneContainer(value: Json): Json {
  if (Array.isArray(value)) return [...value];
  if (typeof value === 'object' && value !== null) return { ...value };
  return value;
}

function applyOp(doc: Json, op: JsonPatchOp): Json {
  const tokens = parsePath(op.path);

  // Whole-document replacement.
  if (tokens.length === 0) {
    if (op.op === 'remove') return {};
    return op.value ?? null;
  }

  const root = cloneContainer(doc ?? {});
  let parent: Json = root;

  for (let i = 0; i < tokens.length - 1; i++) {
    const key = tokens[i] as string;
    if (typeof parent !== 'object' || parent === null) {
      throw new Error(`JSON Patch: path segment "${key}" is not a container`);
    }
    const container = parent as JsonObject & Json[];
    const idx = Array.isArray(parent) ? Number(key) : key;
    const next = Array.isArray(parent)
      ? (parent as Json[])[idx as number]
      : container[idx as string];
    const cloned = cloneContainer(next ?? {});
    if (Array.isArray(parent)) {
      (parent as Json[])[idx as number] = cloned;
    } else {
      (parent as JsonObject)[idx as string] = cloned;
    }
    parent = cloned;
  }

  const last = tokens[tokens.length - 1] as string;
  if (typeof parent !== 'object' || parent === null) {
    throw new Error('JSON Patch: parent of target is not a container');
  }

  if (Array.isArray(parent)) {
    const arr = parent as Json[];
    const index = last === '-' ? arr.length : Number(last);
    if (Number.isNaN(index)) throw new Error(`JSON Patch: bad array index "${last}"`);
    switch (op.op) {
      case 'add':
        arr.splice(index, 0, op.value ?? null);
        break;
      case 'replace':
        arr[index] = op.value ?? null;
        break;
      case 'remove':
        arr.splice(index, 1);
        break;
      default:
        throw new Error(`JSON Patch: unsupported op "${op.op}"`);
    }
  } else {
    const objParent = parent as JsonObject;
    switch (op.op) {
      case 'add':
      case 'replace':
        objParent[last] = op.value ?? null;
        break;
      case 'remove':
        delete objParent[last];
        break;
      default:
        throw new Error(`JSON Patch: unsupported op "${op.op}"`);
    }
  }
  return root;
}

/** Apply a patch to a document, returning a new document. Never mutates input. */
export function applyPatch(doc: JsonObject, ops: JsonPatchOp[]): JsonObject {
  let result: Json = doc;
  for (const op of ops) {
    result = applyOp(result, op);
  }
  if (typeof result !== 'object' || result === null || Array.isArray(result)) {
    // State must stay an object; guard against a patch replacing the root.
    return {};
  }
  return result;
}
