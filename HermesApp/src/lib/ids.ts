/** Compact unique ids (no crypto dependency in Hermes/RN). */
export function makeId(prefix = ''): string {
  const rand = Math.random().toString(36).slice(2, 10);
  return `${prefix}${Date.now().toString(36)}${rand}`;
}
