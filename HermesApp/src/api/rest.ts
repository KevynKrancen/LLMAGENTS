/** Typed REST client for the Hermes backend (threads, routines, artifacts…). */
import { useSettings } from '../state/settings';

export interface ThreadSummary {
  thread_id: string;
  title: string;
  updated_at: string;
}

export interface LoggedMessage {
  role: string;
  content: string;
  created_at: string;
}

export interface RoutineRecord {
  id: string;
  name: string;
  cron: string;
  prompt: string;
  enabled: boolean;
  last_run_at: string | null;
  last_result: string;
}

export interface ArtifactRecord {
  id: string;
  kind: 'html' | 'markdown' | 'table' | 'chart';
  title: string;
  content: string;
  version: number;
  space?: string;
  updated_at: string;
}

export interface WorkspaceNode {
  id: string;
  name: string;
  icon: string;
  items: number;
  /** Artifact id rendered as this folder's custom UI, '' if none. */
  dashboard: string;
  children: WorkspaceNode[];
}

export interface DeviceCommand {
  id: string | null;
  name?: string;
  payload?: Record<string, unknown>;
}

export interface IntegrationStatus {
  connected?: boolean;
  connect_url?: string | null;
  note?: string;
  provider?: string;
  mode?: string;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const { serverUrl, authToken } = useSettings.getState();
  if (!serverUrl) throw new Error('Server URL not configured — open Settings.');
  const response = await fetch(`${serverUrl.replace(/\/$/, '')}${path}`, {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${authToken}`,
      ...(init?.headers ?? {}),
    },
  });
  if (!response.ok) {
    const detail = await response.text().catch(() => '');
    throw new Error(`${path} → ${response.status}: ${detail.slice(0, 200)}`);
  }
  return (await response.json()) as T;
}

export interface ConnectorInstalled {
  id: string;
  kind: 'mcp' | 'openapi' | 'builtin';
  name: string;
  enabled: boolean;
  config: Record<string, unknown>;
  tools: string[];
}

export interface CatalogEntry {
  app: string;
  title: string;
  description: string;
  mcp_url?: string;
  fields: { key: string; label: string; secret?: boolean }[];
}

export interface ReceiptRecord {
  id: string;
  tool: string;
  summary: string;
  reversibility: 'full' | 'partial' | 'none';
  undone: boolean;
  seen: boolean;
  source: string;
  created_at: string;
  can_undo: boolean;
}

export interface HubData {
  unseen_actions: number;
  workspace: WorkspaceNode[];
  recent_threads: ThreadSummary[];
  routines: Pick<RoutineRecord, 'id' | 'name' | 'cron' | 'last_result'>[];
}

export const api = {
  health: () => request<{ ok: boolean; model: string }>('/health'),
  threads: (query = '') =>
    request<ThreadSummary[]>(`/threads${query ? `?query=${encodeURIComponent(query)}` : ''}`),
  threadMessages: (threadId: string) =>
    request<LoggedMessage[]>(`/threads/${encodeURIComponent(threadId)}/messages`),
  artifacts: (space = '') =>
    request<ArtifactRecord[]>(`/artifacts${space ? `?space=${encodeURIComponent(space)}` : ''}`),
  workspace: () => request<WorkspaceNode[]>('/workspace'),
  hub: () => request<HubData>('/hub'),
  ledger: (unseenOnly = false) =>
    request<ReceiptRecord[]>(`/ledger${unseenOnly ? '?unseen_only=true' : ''}`),
  ledgerSeen: () => request<{ ok: boolean }>('/ledger/seen', { method: 'POST' }),
  undoReceipt: (id: string) =>
    request<{ result: string }>(`/ledger/${id}/undo`, { method: 'POST' }),
  routines: () => request<RoutineRecord[]>('/routines'),
  createRoutine: (body: { name: string; cron: string; prompt: string }) =>
    request<{ id: string }>('/routines', { method: 'POST', body: JSON.stringify(body) }),
  toggleRoutine: (id: string, enabled: boolean) =>
    request<{ ok: boolean }>(`/routines/${id}`, {
      method: 'PATCH',
      body: JSON.stringify({ enabled }),
    }),
  deleteRoutine: (id: string) => request<{ ok: boolean }>(`/routines/${id}`, { method: 'DELETE' }),
  registerDevice: (token: string) =>
    request<{ ok: boolean }>('/device/register', { method: 'POST', body: JSON.stringify({ token }) }),
  nextCommand: () => request<DeviceCommand>('/device/next-command'),
  reportCommand: (commandId: string, status: 'success' | 'error', output: string) =>
    request<{ ok: boolean }>('/device/results', {
      method: 'POST',
      body: JSON.stringify({ command_id: commandId, status, output }),
    }),
  integrations: () => request<Record<string, IntegrationStatus>>('/integrations/status'),
  apps: () => request<{ installed: ConnectorInstalled[]; catalog: CatalogEntry[] }>('/apps'),
  addApp: (body: { kind: string; name: string; config: Record<string, unknown> }) =>
    request<{ id: string }>('/apps', { method: 'POST', body: JSON.stringify(body) }),
  toggleApp: (id: string, enabled: boolean) =>
    request<{ ok: boolean }>(`/apps/${id}`, { method: 'PATCH', body: JSON.stringify({ enabled }) }),
  deleteApp: (id: string) => request<{ ok: boolean }>(`/apps/${id}`, { method: 'DELETE' }),
  shortcutsManifest: () =>
    request<{ pack_version: number; shortcuts: { name: string; purpose: string; icloud_url: string }[] }>(
      '/shortcuts/manifest',
    ),
};
