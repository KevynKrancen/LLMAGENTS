/** Artifact detail — live: re-renders as STATE_DELTA updates stream in. */
import React, { useEffect, useState } from 'react';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { Pressable, StyleSheet, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { api, type ArtifactRecord } from '../../src/api/rest';
import { ArtifactCanvas } from '../../src/components/ArtifactCanvas';
import { useChat } from '../../src/state/chat';
import { space, type as typ } from '../../src/theme/tokens';
import { useTheme } from '../../src/theme/useTheme';

export default function ArtifactDetail() {
  const { colors } = useTheme();
  const router = useRouter();
  const { id } = useLocalSearchParams<{ id: string }>();
  const [artifact, setArtifact] = useState<ArtifactRecord | null>(null);

  // Live layer: if the agent is editing this artifact right now, shared
  // state carries the newest version before the REST record updates.
  const liveArtifact = useChat((s) => s.sharedState.artifact) as unknown as
    | ArtifactRecord
    | undefined;
  const current = liveArtifact && liveArtifact.id === id ? liveArtifact : artifact;

  useEffect(() => {
    api
      .artifacts()
      .then((all) => setArtifact(all.find((a) => a.id === id) ?? null))
      .catch(() => setArtifact(null));
  }, [id, liveArtifact?.version]);

  return (
    <SafeAreaView style={[styles.screen, { backgroundColor: colors.bg }]}>
      <View style={styles.header}>
        <Pressable onPress={() => router.back()} hitSlop={10}>
          <Text style={{ color: colors.accent, fontSize: typ.body }}>‹ Back</Text>
        </Pressable>
        <Text style={[styles.title, { color: colors.text }]} numberOfLines={1}>
          {current?.title ?? 'Artifact'}
        </Text>
        <Text style={{ color: colors.subtle, fontSize: typ.micro }}>
          {current ? `v${current.version}` : ''}
        </Text>
      </View>
      {current ? (
        <ArtifactCanvas artifact={current} />
      ) : (
        <Text style={{ color: colors.subtle, padding: space(4) }}>Not found.</Text>
      )}
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1 },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: space(3),
    paddingHorizontal: space(4),
    paddingVertical: space(2),
  },
  title: { flex: 1, fontSize: typ.body, fontWeight: '600', textAlign: 'center' },
});
