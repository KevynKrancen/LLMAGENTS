/** History drawer: slides over the chat, searchable past conversations. */
import React, { useEffect, useState } from 'react';
import {
  FlatList,
  Modal,
  Pressable,
  StyleSheet,
  Text,
  TextInput,
  View,
} from 'react-native';

import { api, type ThreadSummary } from '../api/rest';
import { radius, space, type as typ } from '../theme/tokens';
import { useTheme } from '../theme/useTheme';

interface ThreadDrawerProps {
  visible: boolean;
  onClose: () => void;
  onPick: (threadId: string) => void;
  onNew: () => void;
}

export function ThreadDrawer({ visible, onClose, onPick, onNew }: ThreadDrawerProps) {
  const { colors } = useTheme();
  const [threads, setThreads] = useState<ThreadSummary[]>([]);
  const [query, setQuery] = useState('');
  const [error, setError] = useState('');

  useEffect(() => {
    if (!visible) return;
    api
      .threads(query)
      .then((result) => {
        setThreads(result);
        setError('');
      })
      .catch((e) => setError(String(e.message)));
  }, [visible, query]);

  return (
    <Modal visible={visible} transparent animationType="fade" onRequestClose={onClose}>
      <View style={styles.backdrop}>
        <View style={[styles.drawer, { backgroundColor: colors.bg }]}>
          <View style={styles.header}>
            <Text style={[styles.title, { color: colors.text }]}>Chats</Text>
            <Pressable onPress={onNew} hitSlop={10}>
              <Text style={{ color: colors.accent, fontSize: typ.body }}>＋ New</Text>
            </Pressable>
          </View>
          <TextInput
            style={[styles.search, { backgroundColor: colors.surfaceAlt, color: colors.text }]}
            placeholder="Search conversations"
            placeholderTextColor={colors.subtle}
            value={query}
            onChangeText={setQuery}
          />
          {error ? (
            <Text style={{ color: colors.subtle, fontSize: typ.small }}>{error}</Text>
          ) : (
            <FlatList
              data={threads}
              keyExtractor={(t) => t.thread_id}
              renderItem={({ item }) => (
                <Pressable
                  onPress={() => onPick(item.thread_id)}
                  style={[styles.row, { borderBottomColor: colors.hairline }]}
                >
                  <Text style={{ color: colors.text, fontSize: typ.body }} numberOfLines={1}>
                    {item.title || 'Untitled'}
                  </Text>
                  <Text style={{ color: colors.subtle, fontSize: typ.micro }}>
                    {item.updated_at?.slice(0, 16).replace('T', ' ')}
                  </Text>
                </Pressable>
              )}
            />
          )}
        </View>
        <Pressable style={styles.dismiss} onPress={onClose} />
      </View>
    </Modal>
  );
}

const styles = StyleSheet.create({
  backdrop: { flex: 1, flexDirection: 'row', backgroundColor: 'rgba(0,0,0,0.35)' },
  drawer: { width: '82%', paddingTop: space(16), paddingHorizontal: space(4) },
  dismiss: { flex: 1 },
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: space(3),
  },
  title: { fontSize: typ.title, fontWeight: '600', fontFamily: 'NewYork' },
  search: {
    borderRadius: radius.md,
    padding: space(3),
    fontSize: typ.body,
    marginBottom: space(3),
  },
  row: {
    paddingVertical: space(3),
    borderBottomWidth: StyleSheet.hairlineWidth,
    gap: 2,
  },
});
