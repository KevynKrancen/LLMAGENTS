/**
 * The Hub — the agent-composed surface that replaces a sidebar.
 *
 * One full-screen reveal over the chat: what the agent DID (receipts with
 * undo), what it KEEPS (the workspace tree it grew), and where you TALKED
 * (chats). Nothing here is static app chrome — every section is data the
 * agent composed, and the agent can grow new sections by growing the tree.
 */
import React, { useCallback, useEffect, useState } from 'react';
import { useRouter } from 'expo-router';
import {
  Modal,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { api, type HubData, type ReceiptRecord, type ThreadSummary } from '../api/rest';
import { radius, space, type as typ } from '../theme/tokens';
import { useTheme } from '../theme/useTheme';
import { Symbol } from './Symbol';

interface HubProps {
  visible: boolean;
  onClose: () => void;
  onPickThread: (threadId: string) => void;
  onNewChat: () => void;
}

export function Hub({ visible, onClose, onPickThread, onNewChat }: HubProps) {
  const { colors } = useTheme();
  const router = useRouter();
  const [hub, setHub] = useState<HubData | null>(null);
  const [receipts, setReceipts] = useState<ReceiptRecord[]>([]);
  const [searchResults, setSearchResults] = useState<ThreadSummary[] | null>(null);
  const [query, setQuery] = useState('');

  const load = useCallback(() => {
    api.hub().then(setHub).catch(() => setHub(null));
    api.ledger().then((r) => setReceipts(r.slice(0, 8))).catch(() => setReceipts([]));
  }, []);

  useEffect(() => {
    if (visible) {
      setQuery('');
      setSearchResults(null);
      load();
      api.ledgerSeen().catch(() => undefined);
    }
  }, [visible, load]);

  useEffect(() => {
    if (!query) {
      setSearchResults(null);
      return;
    }
    const t = setTimeout(
      () => api.threads(query).then(setSearchResults).catch(() => setSearchResults([])),
      250,
    );
    return () => clearTimeout(t);
  }, [query]);

  const go = (route: Parameters<typeof router.push>[0]) => {
    onClose();
    router.push(route);
  };

  const Section = ({ title, children }: { title: string; children: React.ReactNode }) => (
    <View style={styles.section}>
      <Text style={[styles.sectionTitle, { color: colors.subtle }]}>{title}</Text>
      {children}
    </View>
  );

  return (
    <Modal visible={visible} animationType="slide" onRequestClose={onClose}>
      <SafeAreaView style={[styles.screen, { backgroundColor: colors.bg }]}>
        <View style={styles.header}>
          <Text style={[styles.title, { color: colors.text }]}>Hermes keeps</Text>
          <Pressable onPress={onClose} hitSlop={12}>
            <Symbol name="xmark" size={17} />
          </Pressable>
        </View>

        <ScrollView contentContainerStyle={{ paddingHorizontal: space(5), paddingBottom: space(8) }}>
          {/* While you were away — receipts with undo */}
          {receipts.length > 0 && (
            <Section title="WHILE YOU WERE AWAY">
              {receipts.map((receipt) => (
                <View key={receipt.id} style={[styles.receipt, { borderBottomColor: colors.hairline }]}>
                  <View
                    style={[
                      styles.dot,
                      {
                        backgroundColor: receipt.undone
                          ? colors.subtle
                          : receipt.reversibility === 'none'
                            ? colors.accent
                            : colors.success,
                      },
                    ]}
                  />
                  <View style={{ flex: 1 }}>
                    <Text
                      style={{
                        color: colors.text,
                        fontSize: typ.small,
                        textDecorationLine: receipt.undone ? 'line-through' : 'none',
                      }}
                      numberOfLines={2}
                    >
                      {receipt.summary}
                    </Text>
                    <Text style={{ color: colors.subtle, fontSize: typ.micro }}>
                      {receipt.created_at?.slice(5, 16).replace('T', ' ')} · {receipt.source}
                    </Text>
                  </View>
                  {receipt.can_undo && !receipt.undone && (
                    <Pressable
                      onPress={() => api.undoReceipt(receipt.id).then(load).catch(() => undefined)}
                      hitSlop={8}
                    >
                      <Text style={{ color: colors.accent, fontSize: typ.small }}>Undo</Text>
                    </Pressable>
                  )}
                </View>
              ))}
            </Section>
          )}

          {/* The workspace the agent grew */}
          <Section title="YOUR SPACE">
            {(hub?.workspace.length ?? 0) === 0 ? (
              <Text style={{ color: colors.subtle, fontSize: typ.small }}>
                Unshaped — tell Hermes what to keep and it takes form here.
              </Text>
            ) : (
              hub!.workspace.map((node) => (
                <Pressable
                  key={node.id}
                  onPress={() => go({ pathname: '/space/[id]', params: { id: node.id } })}
                  style={styles.row}
                >
                  <Symbol name={node.icon} size={17} tint={colors.accent} />
                  <Text style={{ color: colors.text, fontSize: typ.body, flex: 1 }}>
                    {node.name}
                  </Text>
                  <Text style={{ color: colors.subtle, fontSize: typ.micro }}>
                    {node.children.length > 0 ? `${node.children.length} ▸` : node.items || ''}
                  </Text>
                </Pressable>
              ))
            )}
          </Section>

          {/* Routines glance */}
          {(hub?.routines.length ?? 0) > 0 && (
            <Section title="RHYTHMS">
              {hub!.routines.map((routine) => (
                <Pressable key={routine.id} onPress={() => go('/routines')} style={styles.row}>
                  <Symbol name="arrow.triangle.2.circlepath" size={15} tint={colors.accent} />
                  <Text style={{ color: colors.text, fontSize: typ.small, flex: 1 }}>
                    {routine.name}
                  </Text>
                  <Text style={{ color: colors.subtle, fontSize: typ.micro }}>{routine.cron}</Text>
                </Pressable>
              ))}
            </Section>
          )}

          {/* Conversations */}
          <Section title="CONVERSATIONS">
            <View style={styles.searchRow}>
              <TextInput
                style={[styles.search, { backgroundColor: colors.surfaceAlt, color: colors.text }]}
                placeholder="Search everything said"
                placeholderTextColor={colors.subtle}
                value={query}
                onChangeText={setQuery}
              />
              <Pressable
                onPress={() => {
                  onNewChat();
                  onClose();
                }}
                hitSlop={8}
              >
                <Symbol name="square.and.pencil" size={19} tint={colors.accent} />
              </Pressable>
            </View>
            {(searchResults ?? hub?.recent_threads ?? []).map((thread) => (
              <Pressable
                key={thread.thread_id}
                onPress={() => {
                  onPickThread(thread.thread_id);
                  onClose();
                }}
                style={[styles.threadRow, { borderBottomColor: colors.hairline }]}
              >
                <Text style={{ color: colors.text, fontSize: typ.small }} numberOfLines={1}>
                  {thread.title || 'Untitled'}
                </Text>
                <Text style={{ color: colors.subtle, fontSize: typ.micro }}>
                  {thread.updated_at?.slice(0, 16).replace('T', ' ')}
                </Text>
              </Pressable>
            ))}
          </Section>

          {/* System, quiet at the bottom */}
          <View style={styles.systemRow}>
            {[
              { icon: 'puzzlepiece.extension', label: 'Connectors', route: '/connectors' },
              { icon: 'doc.text', label: 'Artifacts', route: '/artifacts' },
              { icon: 'gearshape', label: 'Settings', route: '/settings' },
            ].map((entry) => (
              <Pressable
                key={entry.route}
                onPress={() => go(entry.route as never)}
                style={[styles.systemChip, { borderColor: colors.hairline }]}
              >
                <Symbol name={entry.icon} size={14} />
                <Text style={{ color: colors.subtle, fontSize: typ.small }}>{entry.label}</Text>
              </Pressable>
            ))}
          </View>
        </ScrollView>
      </SafeAreaView>
    </Modal>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1 },
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingHorizontal: space(5),
    paddingVertical: space(3),
  },
  title: { fontSize: typ.title, fontWeight: '600', fontFamily: 'NewYork' },
  section: { marginBottom: space(6) },
  sectionTitle: { fontSize: typ.micro, letterSpacing: 1.4, marginBottom: space(2) },
  receipt: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: space(3),
    paddingVertical: space(2.5),
    borderBottomWidth: StyleSheet.hairlineWidth,
  },
  dot: { width: 7, height: 7, borderRadius: 4 },
  row: { flexDirection: 'row', alignItems: 'center', gap: space(3), paddingVertical: space(2.5) },
  searchRow: { flexDirection: 'row', alignItems: 'center', gap: space(3), marginBottom: space(2) },
  search: { flex: 1, borderRadius: radius.md, padding: space(2.5), fontSize: typ.small },
  threadRow: {
    paddingVertical: space(2.5),
    borderBottomWidth: StyleSheet.hairlineWidth,
    gap: 2,
  },
  systemRow: { flexDirection: 'row', gap: space(2), marginTop: space(2) },
  systemChip: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: space(1.5),
    borderWidth: StyleSheet.hairlineWidth,
    borderRadius: radius.lg,
    paddingHorizontal: space(3),
    paddingVertical: space(2),
  },
});
