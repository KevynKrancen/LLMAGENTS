import React, { useCallback, useEffect, useState } from 'react';
import { useRouter } from 'expo-router';
import { FlatList, Pressable, RefreshControl, StyleSheet, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { api, type ArtifactRecord } from '../src/api/rest';
import { radius, space, type as typ } from '../src/theme/tokens';
import { useTheme } from '../src/theme/useTheme';

const KIND_ICON: Record<string, string> = {
  html: '⧉',
  markdown: '¶',
  table: '▦',
  chart: '𝄜',
};

export default function Artifacts() {
  const { colors } = useTheme();
  const router = useRouter();
  const [artifacts, setArtifacts] = useState<ArtifactRecord[]>([]);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState('');

  const load = useCallback(() => {
    setRefreshing(true);
    api
      .artifacts()
      .then((result) => {
        setArtifacts(result);
        setError('');
      })
      .catch((e) => setError(String(e.message)))
      .finally(() => setRefreshing(false));
  }, []);

  useEffect(load, [load]);

  return (
    <SafeAreaView style={[styles.screen, { backgroundColor: colors.bg }]}>
      <Text style={[styles.title, { color: colors.text }]}>Artifacts</Text>
      {error ? <Text style={{ color: colors.subtle, padding: space(4) }}>{error}</Text> : null}
      <FlatList
        data={artifacts}
        keyExtractor={(artifact) => artifact.id}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={load} />}
        contentContainerStyle={{ padding: space(4), gap: space(3) }}
        ListEmptyComponent={
          !error ? (
            <Text style={{ color: colors.subtle, textAlign: 'center', marginTop: space(10) }}>
              Ask Hermes to create a report, dashboard, or plan — it appears here.
            </Text>
          ) : null
        }
        renderItem={({ item }) => (
          <Pressable
            onPress={() => router.push({ pathname: '/artifact/[id]', params: { id: item.id } })}
            style={[styles.card, { backgroundColor: colors.surface, borderColor: colors.hairline }]}
          >
            <Text style={{ fontSize: 18, color: colors.accent }}>{KIND_ICON[item.kind] ?? '⧉'}</Text>
            <View style={{ flex: 1 }}>
              <Text style={{ color: colors.text, fontSize: typ.body, fontWeight: '600' }}>
                {item.title}
              </Text>
              <Text style={{ color: colors.subtle, fontSize: typ.micro }}>
                v{item.version} · {item.updated_at?.slice(0, 16).replace('T', ' ')}
              </Text>
            </View>
          </Pressable>
        )}
      />
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
  card: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: space(3),
    borderRadius: radius.md,
    borderWidth: StyleSheet.hairlineWidth,
    padding: space(4),
  },
});
