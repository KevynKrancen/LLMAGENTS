/** Connectors — install apps; their tools attach to Hermes automatically. */
import React, { useCallback, useEffect, useState } from 'react';
import {
  FlatList,
  Pressable,
  RefreshControl,
  StyleSheet,
  Switch,
  Text,
  TextInput,
  View,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { api, type CatalogEntry, type ConnectorInstalled } from '../src/api/rest';
import { Sheet } from '../src/components/Sheet';
import { radius, space, type as typ } from '../src/theme/tokens';
import { useTheme } from '../src/theme/useTheme';

const KIND_BADGE: Record<string, string> = { mcp: 'MCP', openapi: 'API', builtin: 'App' };

type AddMode =
  | { type: 'catalog'; entry: CatalogEntry }
  | { type: 'mcp' }
  | { type: 'openapi' }
  | null;

export default function Connectors() {
  const { colors } = useTheme();
  const [installed, setInstalled] = useState<ConnectorInstalled[]>([]);
  const [catalog, setCatalog] = useState<CatalogEntry[]>([]);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState('');
  const [addMode, setAddMode] = useState<AddMode>(null);
  const [form, setForm] = useState<Record<string, string>>({});

  const load = useCallback(() => {
    setRefreshing(true);
    api
      .apps()
      .then((result) => {
        setInstalled(result.installed);
        setCatalog(result.catalog);
        setError('');
      })
      .catch((e) => setError(String(e.message)))
      .finally(() => setRefreshing(false));
  }, []);

  useEffect(load, [load]);

  const installedApps = new Set(
    installed.map((connector) => String(connector.config.app ?? connector.name)),
  );
  const available = catalog.filter((entry) => !installedApps.has(entry.app));

  const submit = async () => {
    try {
      if (addMode?.type === 'catalog') {
        const entry = addMode.entry;
        const config: Record<string, unknown> = { app: entry.app };
        for (const field of entry.fields) config[field.key] = form[field.key] ?? '';
        await api.addApp({ kind: 'builtin', name: entry.app, config });
      } else if (addMode?.type === 'mcp') {
        await api.addApp({
          kind: 'mcp',
          name: form.name ?? 'mcp',
          config: { url: form.url ?? '' },
        });
      } else if (addMode?.type === 'openapi') {
        const config: Record<string, unknown> = { spec_url: form.spec_url ?? '' };
        if (form.auth?.includes(':')) {
          const [key, ...rest] = form.auth.split(':');
          config.headers = { [key!.trim()]: rest.join(':').trim() };
        }
        await api.addApp({ kind: 'openapi', name: form.name ?? 'api', config });
      }
      setAddMode(null);
      setForm({});
      load();
    } catch (e) {
      setError(String((e as Error).message));
    }
  };

  const input = (key: string, placeholder: string, secret = false) => (
    <TextInput
      key={key}
      style={[styles.input, { color: colors.text, borderColor: colors.hairline }]}
      placeholder={placeholder}
      placeholderTextColor={colors.subtle}
      autoCapitalize="none"
      autoCorrect={false}
      secureTextEntry={secret}
      value={form[key] ?? ''}
      onChangeText={(value) => setForm((f) => ({ ...f, [key]: value }))}
    />
  );

  return (
    <SafeAreaView style={[styles.screen, { backgroundColor: colors.bg }]}>
      <Text style={[styles.title, { color: colors.text }]}>Connectors</Text>
      <Text style={{ color: colors.subtle, fontSize: typ.small, paddingHorizontal: space(4) }}>
        Add an app and its tools attach to Hermes automatically.
      </Text>
      {error ? (
        <Text style={{ color: colors.danger, padding: space(4) }} numberOfLines={2}>
          {error}
        </Text>
      ) : null}

      <FlatList
        data={installed}
        keyExtractor={(connector) => connector.id}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={load} />}
        contentContainerStyle={{ padding: space(4), gap: space(3) }}
        renderItem={({ item }) => (
          <View
            style={[styles.card, { backgroundColor: colors.surface, borderColor: colors.hairline }]}
          >
            <View style={{ flex: 1 }}>
              <View style={styles.nameRow}>
                <Text style={{ color: colors.text, fontSize: typ.body, fontWeight: '600' }}>
                  {item.name}
                </Text>
                <Text style={[styles.badge, { color: colors.accent, borderColor: colors.accent }]}>
                  {KIND_BADGE[item.kind]}
                </Text>
              </View>
              <Text style={{ color: colors.subtle, fontSize: typ.micro }} numberOfLines={2}>
                {item.tools.length > 0
                  ? `${item.tools.length} tool${item.tools.length > 1 ? 's' : ''}: ${item.tools
                      .slice(0, 4)
                      .join(', ')}${item.tools.length > 4 ? '…' : ''}`
                  : item.enabled
                    ? 'no tools loaded (check config)'
                    : 'disabled'}
              </Text>
              <Pressable onPress={() => api.deleteApp(item.id).then(load).catch(() => undefined)}>
                <Text style={{ color: colors.danger, fontSize: typ.micro, marginTop: space(1) }}>
                  Remove
                </Text>
              </Pressable>
            </View>
            <Switch
              value={item.enabled}
              onValueChange={(enabled) =>
                api.toggleApp(item.id, enabled).then(load).catch(() => undefined)
              }
              trackColor={{ true: colors.accent }}
            />
          </View>
        )}
        ListFooterComponent={
          <View style={{ gap: space(3) }}>
            {available.length > 0 && (
              <Text style={[styles.sectionTitle, { color: colors.subtle }]}>CATALOG</Text>
            )}
            {available.map((entry) => (
              <Pressable
                key={entry.app}
                onPress={() => {
                  setForm({});
                  setAddMode({ type: 'catalog', entry });
                }}
                style={[
                  styles.card,
                  { backgroundColor: colors.surface, borderColor: colors.hairline },
                ]}
              >
                <View style={{ flex: 1 }}>
                  <Text style={{ color: colors.text, fontSize: typ.body, fontWeight: '600' }}>
                    {entry.title}
                  </Text>
                  <Text style={{ color: colors.subtle, fontSize: typ.micro }}>
                    {entry.description}
                  </Text>
                </View>
                <Text style={{ color: colors.accent, fontSize: typ.body }}>＋</Text>
              </Pressable>
            ))}
            <Text style={[styles.sectionTitle, { color: colors.subtle }]}>ADD YOUR OWN</Text>
            <View style={styles.addRow}>
              <Pressable
                onPress={() => {
                  setForm({});
                  setAddMode({ type: 'mcp' });
                }}
                style={[styles.addButton, { borderColor: colors.hairline }]}
              >
                <Text style={{ color: colors.subtle, fontSize: typ.small }}>＋ MCP server</Text>
              </Pressable>
              <Pressable
                onPress={() => {
                  setForm({});
                  setAddMode({ type: 'openapi' });
                }}
                style={[styles.addButton, { borderColor: colors.hairline }]}
              >
                <Text style={{ color: colors.subtle, fontSize: typ.small }}>＋ API (OpenAPI)</Text>
              </Pressable>
            </View>
          </View>
        }
      />

      <Sheet visible={addMode !== null} onClose={() => setAddMode(null)}>
        {addMode?.type === 'catalog' && (
          <>
            <Text style={[styles.sheetTitle, { color: colors.text }]}>{addMode.entry.title}</Text>
            <Text style={{ color: colors.subtle, fontSize: typ.small, marginBottom: space(3) }}>
              {addMode.entry.description}
            </Text>
            {addMode.entry.fields.map((field) => input(field.key, field.label, field.secret))}
          </>
        )}
        {addMode?.type === 'mcp' && (
          <>
            <Text style={[styles.sheetTitle, { color: colors.text }]}>Connect MCP server</Text>
            {input('name', 'Name (e.g. notion)')}
            {input('url', 'https://mcp.example.com/mcp')}
          </>
        )}
        {addMode?.type === 'openapi' && (
          <>
            <Text style={[styles.sheetTitle, { color: colors.text }]}>Connect an API</Text>
            {input('name', 'Name (e.g. myservice)')}
            {input('spec_url', 'OpenAPI spec URL (…/openapi.json)')}
            {input('auth', 'Auth header (optional) — Authorization: Bearer …')}
          </>
        )}
        <Pressable onPress={submit} style={[styles.connect, { backgroundColor: colors.accent }]}>
          <Text style={{ color: colors.onAccent, fontWeight: '600' }}>Connect</Text>
        </Pressable>
      </Sheet>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1 },
  title: {
    fontSize: typ.title,
    fontWeight: '600',
    fontFamily: 'NewYork',
    paddingHorizontal: space(4),
    paddingTop: space(2),
  },
  sectionTitle: { fontSize: typ.micro, letterSpacing: 1.2, marginTop: space(2) },
  card: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: space(3),
    borderRadius: radius.md,
    borderWidth: StyleSheet.hairlineWidth,
    padding: space(4),
  },
  nameRow: { flexDirection: 'row', alignItems: 'center', gap: space(2) },
  badge: {
    fontSize: 9,
    borderWidth: 1,
    borderRadius: 5,
    paddingHorizontal: 4,
    paddingVertical: 1,
    overflow: 'hidden',
  },
  addRow: { flexDirection: 'row', gap: space(3) },
  addButton: {
    flex: 1,
    borderWidth: 1,
    borderStyle: 'dashed',
    borderRadius: radius.md,
    paddingVertical: space(3),
    alignItems: 'center',
  },
  sheetTitle: { fontSize: typ.heading, fontWeight: '600', marginBottom: space(3) },
  input: {
    borderWidth: StyleSheet.hairlineWidth,
    borderRadius: radius.md,
    padding: space(3),
    fontSize: typ.body,
    marginBottom: space(3),
  },
  connect: { borderRadius: radius.md, paddingVertical: space(3.5), alignItems: 'center' },
});
