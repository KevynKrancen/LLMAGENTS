/** A space — dynamic collection of items the agent keeps for the user. */
import React, { useCallback, useEffect, useState } from 'react';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { FlatList, Pressable, RefreshControl, StyleSheet, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { api, type ArtifactRecord, type SpaceRecord } from '../../src/api/rest';
import { radius, space as sp, type as typ } from '../../src/theme/tokens';
import { useTheme } from '../../src/theme/useTheme';

export default function Space() {
  const { colors } = useTheme();
  const router = useRouter();
  const { id } = useLocalSearchParams<{ id: string }>();
  const [items, setItems] = useState<ArtifactRecord[]>([]);
  const [meta, setMeta] = useState<SpaceRecord | null>(null);
  const [refreshing, setRefreshing] = useState(false);

  const load = useCallback(() => {
    if (!id) return;
    setRefreshing(true);
    Promise.all([api.artifacts(id), api.spaces()])
      .then(([artifacts, spaces]) => {
        setItems(artifacts);
        setMeta(spaces.find((space) => space.id === id) ?? null);
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
        <Text style={[styles.title, { color: colors.text }]}>
          {meta ? `${meta.icon} ${meta.name}` : ''}
        </Text>
        <View style={{ width: 44 }} />
      </View>
      <FlatList
        data={items}
        keyExtractor={(item) => item.id}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={load} />}
        contentContainerStyle={{ padding: sp(4), gap: sp(3) }}
        ListEmptyComponent={
          <Text style={{ color: colors.subtle, textAlign: 'center', marginTop: sp(10) }}>
            Nothing here yet — tell Hermes to save something into this space.
          </Text>
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
            <Text style={{ color: colors.subtle, fontSize: typ.micro }}>
              {item.updated_at?.slice(0, 16).replace('T', ' ')}
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
  card: {
    borderRadius: radius.md,
    borderWidth: StyleSheet.hairlineWidth,
    padding: sp(4),
    gap: sp(1.5),
  },
});
