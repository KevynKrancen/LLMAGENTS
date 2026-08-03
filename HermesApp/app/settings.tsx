import React, { useEffect, useState } from 'react';
import * as Linking from 'expo-linking';
import {
  Pressable,
  ScrollView,
  StyleSheet,
  Switch,
  Text,
  TextInput,
  View,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { api, type IntegrationStatus } from '../src/api/rest';
import { ModelSheet } from '../src/components/ModelSheet';
import { registerForPush } from '../src/device/push';
import { useSettings } from '../src/state/settings';
import { radius, space, type as typ } from '../src/theme/tokens';
import { useTheme } from '../src/theme/useTheme';

export default function Settings() {
  const { colors } = useTheme();
  const settings = useSettings();
  const [serverUrl, setServerUrl] = useState(settings.serverUrl);
  const [authToken, setAuthToken] = useState(settings.authToken);
  const [status, setStatus] = useState<Record<string, IntegrationStatus> | null>(null);
  const [pushState, setPushState] = useState('');
  const [modelOpen, setModelOpen] = useState(false);
  const [health, setHealth] = useState('');

  useEffect(() => {
    if (settings.serverUrl) {
      api.integrations().then(setStatus).catch(() => setStatus(null));
    }
  }, [settings.serverUrl, settings.authToken]);

  const saveServer = async () => {
    settings.setServer(serverUrl.trim().replace(/\/$/, ''), authToken.trim());
    try {
      const result = await api.health();
      setHealth(`Connected ✓ (${result.model})`);
    } catch (e) {
      setHealth(`Failed: ${(e as Error).message}`);
    }
  };

  const enablePush = async () => {
    try {
      setPushState((await registerForPush()) ? 'Registered ✓' : 'Permission denied');
    } catch (e) {
      setPushState(String((e as Error).message));
    }
  };

  const Row = ({ label, children }: { label: string; children: React.ReactNode }) => (
    <View style={styles.row}>
      <Text style={{ color: colors.text, fontSize: typ.body }}>{label}</Text>
      {children}
    </View>
  );

  const dot = (connected?: boolean) => (
    <Text style={{ color: connected ? colors.success : colors.subtle }}>
      {connected ? '● Connected' : '○ Not set up'}
    </Text>
  );

  return (
    <SafeAreaView style={[styles.screen, { backgroundColor: colors.bg }]}>
      <ScrollView contentContainerStyle={{ padding: space(4), gap: space(5) }}>
        <Text style={[styles.title, { color: colors.text }]}>Settings</Text>

        <View style={styles.section}>
          <Text style={[styles.sectionTitle, { color: colors.subtle }]}>SERVER</Text>
          <TextInput
            style={[styles.input, { color: colors.text, borderColor: colors.hairline }]}
            placeholder="https://your-server:8787"
            placeholderTextColor={colors.subtle}
            autoCapitalize="none"
            autoCorrect={false}
            value={serverUrl}
            onChangeText={setServerUrl}
          />
          <TextInput
            style={[styles.input, { color: colors.text, borderColor: colors.hairline }]}
            placeholder="API token"
            placeholderTextColor={colors.subtle}
            autoCapitalize="none"
            secureTextEntry
            value={authToken}
            onChangeText={setAuthToken}
          />
          <Pressable onPress={saveServer} style={[styles.button, { backgroundColor: colors.accent }]}>
            <Text style={{ color: colors.onAccent, fontWeight: '600' }}>Save & test</Text>
          </Pressable>
          {health ? <Text style={{ color: colors.subtle, fontSize: typ.small }}>{health}</Text> : null}
        </View>

        <View style={styles.section}>
          <Text style={[styles.sectionTitle, { color: colors.subtle }]}>INTELLIGENCE</Text>
          <Row label="Model">
            <Pressable onPress={() => setModelOpen(true)}>
              <Text style={{ color: colors.accent }}>
                {settings.provider}:{settings.model} ›
              </Text>
            </Pressable>
          </Row>
          <Row label="Long-term memory">
            <Switch
              value={settings.memoryEnabled}
              onValueChange={settings.setMemoryEnabled}
              trackColor={{ true: colors.accent }}
            />
          </Row>
        </View>

        <View style={styles.section}>
          <Text style={[styles.sectionTitle, { color: colors.subtle }]}>CONNECTED ACCOUNTS</Text>
          <Row label="Google (Gmail · Calendar)">
            {status?.google?.connected ? (
              dot(true)
            ) : (
              <Pressable
                onPress={() =>
                  settings.serverUrl &&
                  Linking.openURL(`${settings.serverUrl}/auth/google/start`)
                }
              >
                <Text style={{ color: colors.accent }}>Sign in ›</Text>
              </Pressable>
            )}
          </Row>
          <Row label="Apple Mail">{dot(status?.apple_mail?.connected)}</Row>
          <Row label="WhatsApp">{dot(status?.whatsapp?.connected)}</Row>
          <Row label="Web search">{dot(status?.web_search?.connected)}</Row>
          <Row label="YouTube">{dot(status?.youtube?.connected)}</Row>
        </View>

        <View style={styles.section}>
          <Text style={[styles.sectionTitle, { color: colors.subtle }]}>PHONE</Text>
          <Row label="Push notifications">
            <Pressable onPress={enablePush}>
              <Text style={{ color: colors.accent }}>{pushState || 'Enable ›'}</Text>
            </Pressable>
          </Row>
          <ShortcutPack />
        </View>
      </ScrollView>
      <ModelSheet visible={modelOpen} onClose={() => setModelOpen(false)} />
    </SafeAreaView>
  );
}

function ShortcutPack() {
  const { colors } = useTheme();
  const [shortcuts, setShortcuts] = useState<{ name: string; purpose: string; icloud_url: string }[]>([]);

  useEffect(() => {
    api
      .shortcutsManifest()
      .then((manifest) => setShortcuts(manifest.shortcuts))
      .catch(() => setShortcuts([]));
  }, []);

  if (shortcuts.length === 0) return null;
  return (
    <View style={{ gap: space(2), marginTop: space(2) }}>
      <Text style={{ color: colors.subtle, fontSize: typ.small }}>
        Shortcut pack — lets Hermes act inside other apps:
      </Text>
      {shortcuts.map((shortcut) => (
        <View key={shortcut.name} style={styles.shortcutRow}>
          <View style={{ flex: 1 }}>
            <Text style={{ color: colors.text, fontSize: typ.small }}>{shortcut.name}</Text>
            <Text style={{ color: colors.subtle, fontSize: typ.micro }}>{shortcut.purpose}</Text>
          </View>
          {shortcut.icloud_url ? (
            <Pressable onPress={() => Linking.openURL(shortcut.icloud_url)}>
              <Text style={{ color: colors.accent, fontSize: typ.small }}>Install ›</Text>
            </Pressable>
          ) : (
            <Text style={{ color: colors.subtle, fontSize: typ.micro }}>build manually</Text>
          )}
        </View>
      ))}
    </View>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1 },
  title: { fontSize: typ.title, fontWeight: '600', fontFamily: 'NewYork' },
  section: { gap: space(3) },
  sectionTitle: { fontSize: typ.micro, letterSpacing: 1.2 },
  input: {
    borderWidth: StyleSheet.hairlineWidth,
    borderRadius: radius.md,
    padding: space(3),
    fontSize: typ.body,
  },
  button: { borderRadius: radius.md, paddingVertical: space(3), alignItems: 'center' },
  row: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    minHeight: 32,
  },
  shortcutRow: { flexDirection: 'row', alignItems: 'center', gap: space(2) },
});
