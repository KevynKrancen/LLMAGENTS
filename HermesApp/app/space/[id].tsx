/** A workspace folder — child folders plus the items Hermes keeps here. */
import React, { useCallback, useEffect, useState } from 'react';
import { useLocalSearchParams, useRouter } from 'expo-router';
import {
  FlatList,
  Pressable,
  RefreshControl,
  StyleSheet,
  Text,
  View,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { api, type ArtifactRecord, type WorkspaceNode } from '../../src/api/rest';
import { ArtifactCanvas } from '../../src/components/ArtifactCanvas';
import { Symbol } from '../../src/components/Symbol';
import { radius, space as sp, type as typ } from '../../src/theme/tokens';
import { useTheme } from '../../src/theme/useTheme';

function findNode(tree: WorkspaceNode[], id: string): WorkspaceNode | null {
  for (const node of tree) {
    if (node.id === id) return node;
    const inner = findNode(node.children, id);
    if (inner) return inner;
  }
  return null;
}

export default function SpaceScreen() {
  const { colors } = useTheme();
  const router = useRouter();
  const { id } = useLocalSearchParams<{ id: string }>();
  const [items, setItems] = useState<ArtifactRecord[]>([]);
  const [node, setNode] = useState<WorkspaceNode | null>(null);
  const [dashboard, setDashboard] = useState<ArtifactRecord | null>(null);
  const [refreshing, setRefreshing] = useState(false);

  const load = useCallback(() => {
    if (!id) return;
    setRefreshing(true);
    Promise.all([api.artifacts(id), api.workspace(), api.artifacts()])
      .then(([artifacts, tree, all]) => {
        const found = findNode(tree, id);
        setNode(found);
        setDashboard(
          found?.dashboard ? (all.find((a) => a.id === found.dashboard) ?? null) : null,
        );
        // The dashboard is the folder's face — don't repeat it in the list.
        setItems(artifacts.filter((a) => a.id !== found?.dashboard));
      })
      .catch(() => undefined)
      .finally(() => setRefreshing(false));
  }, [id]);

  useEffect(load, [load]);

  return (
    <SafeAreaView style={[styles.screen, { backgroundColor: colors.bg }]}>
      <View style={styles.header}>
        <Pressable onPress={() => router.back()} hitSlop={10}>
          <Text style={{ color: colors.accent, fontSize: typ.body }}>‹ Back</Text>
        </Pressable>
        <View style={styles.titleRow}>
          {node && <Symbol name={node.icon} size={16} tint={colors.accent} />}
          <Text style={[styles.title, { color: colors.text }]}>{node?.name ?? ''}</Text>
        </View>
        <View style={{ width: 44 }} />
      </View>

      {dashboard && (
        <Pressable
          style={styles.dashboard}
          onPress={() =>
            router.push({ pathname: '/artifact/[id]', params: { id: dashboard.id } })
          }
        >
          <ArtifactCanvas artifact={dashboard} />
        </Pressable>
      )}

      {node && node.children.length > 0 && (
        <View style={styles.folderGrid}>
          {node.children.map((child) => (
            <Pressable
              key={child.id}
              onPress={() => router.push({ pathname: '/space/[id]', params: { id: child.id } })}
              style={[styles.folder, { backgroundColor: colors.surfaceAlt }]}
            >
              <Symbol name={child.icon} size={15} tint={colors.accent} />
              <Text style={{ color: colors.text, fontSize: typ.micro }} numberOfLines={1}>
                {child.name}
              </Text>
            </Pressable>
          ))}
        </View>
      )}

      <FlatList
        data={items}
        keyExtractor={(item) => item.id}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={load} />}
        contentContainerStyle={{ padding: sp(4), gap: sp(3) }}
        ListEmptyComponent={
          (node?.children.length ?? 0) === 0 ? (
            <Text style={{ color: colors.subtle, textAlign: 'center', marginTop: sp(10) }}>
              Nothing here yet — tell Hermes to keep something in {node?.name ?? 'this folder'}.
            </Text>
          ) : null
        }
        renderItem={({ item }) => (
          <Pressable
            onPress={() => router.push({ pathname: '/artifact/[id]', params: { id: item.id } })}
            style={[styles.card, { backgroundColor: colors.surface, borderColor: colors.hairline }]}
          >
            <Text style={{ color: colors.text, fontSize: typ.body, fontWeight: '600' }}>
              {item.title}
            </Text>
            <Text style={{ color: colors.subtle, fontSize: typ.small }} numberOfLines={2}>
              {item.content.replace(/[#*`>]/g, '').slice(0, 140)}
            </Text>
          </Pressable>
        )}
      />
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1 },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: sp(4),
    paddingVertical: sp(2),
  },
  title: { fontSize: typ.body, fontWeight: '600' },
  titleRow: { flexDirection: 'row', alignItems: 'center', gap: sp(2) },
  dashboard: { height: 300, marginHorizontal: sp(4), borderRadius: radius.md, overflow: 'hidden' },
  folderGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: sp(2),
    paddingHorizontal: sp(4),
    paddingTop: sp(2),
  },
  folder: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: sp(2),
    borderRadius: radius.lg,
    paddingHorizontal: sp(3),
    paddingVertical: sp(2),
  },
  card: {
    borderRadius: radius.md,
    borderWidth: StyleSheet.hairlineWidth,
    padding: sp(4),
    gap: sp(1.5),
  },
});
