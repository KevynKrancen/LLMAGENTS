/** Settings store — server connection, provider/model, preferences. */
import AsyncStorage from '@react-native-async-storage/async-storage';
import { create } from 'zustand';
import { createJSONStorage, persist } from 'zustand/middleware';

export type Provider = 'anthropic' | 'openai' | 'google_genai' | 'openrouter' | 'ollama';

export const PROVIDERS: { key: Provider; label: string; defaultModel: string }[] = [
  { key: 'anthropic', label: 'Anthropic', defaultModel: 'claude-sonnet-5' },
  { key: 'openai', label: 'OpenAI', defaultModel: 'gpt-5.5' },
  { key: 'google_genai', label: 'Google', defaultModel: 'gemini-3.6-flash' },
  { key: 'openrouter', label: 'OpenRouter', defaultModel: 'meta-llama/llama-4-maverick' },
  { key: 'ollama', label: 'Ollama', defaultModel: 'qwen3' },
];

interface SettingsState {
  serverUrl: string;
  authToken: string;
  provider: Provider;
  model: string;
  memoryEnabled: boolean;
  userName: string;
  setServer: (url: string, token: string) => void;
  setModel: (provider: Provider, model: string) => void;
  setMemoryEnabled: (enabled: boolean) => void;
  setUserName: (name: string) => void;
  /** provider:model spec forwarded to the backend on every run. */
  modelSpec: () => string;
}

export const useSettings = create<SettingsState>()(
  persist(
    (set, get) => ({
      serverUrl: '',
      authToken: '',
      provider: 'anthropic',
      model: 'claude-sonnet-5',
      memoryEnabled: true,
      userName: 'Kevyn',
      setServer: (serverUrl, authToken) => set({ serverUrl, authToken }),
      setModel: (provider, model) => set({ provider, model }),
      setMemoryEnabled: (memoryEnabled) => set({ memoryEnabled }),
      setUserName: (userName) => set({ userName }),
      modelSpec: () => `${get().provider}:${get().model}`,
    }),
    {
      name: 'hermes-settings',
      storage: createJSONStorage(() => AsyncStorage),
    },
  ),
);
