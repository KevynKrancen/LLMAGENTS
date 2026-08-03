/**
 * The ＋ sheet — Spaces, not buttons.
 *
 * Agent actions (music, shortcuts, email…) happen invisibly through
 * conversation; this sheet only surfaces the user's living spaces:
 * Routines, Notes, Connectors, and anything they created by simply asking
 * Hermes ("make me a Recipes space"). Fully dynamic.
 */
import React, { useEffect, useState } from 'react';
import { useRouter } from 'expo-router';
import { Pressable, StyleSheet, Text, View } from 'react-native';

import { api, type SpaceRecord } from '../api/rest';
import { radius, space as sp, type as typ } from '../theme/tokens';
import { useTheme } from '../theme/useTheme';
import { Sheet } from './Sheet';

const FIXED: { id: string; name: string; icon: string; route: string }[] = [
  { id: '_routines', name: 'Routines', icon: '↻', route: '/routines' },
  { id: '_connectors', name: 'Connectors', icon: '🧩', route: '/connectors' },
];

interface CapabilitySheetProps {
  visible: boolean;
  onClose: () => void;
  onPrompt: (prompt: string, autosend: boolean) => void;
}

export function CapabilitySheet({ visible, onClose, onPrompt }: CapabilitySheetProps) {
  const { colors } = useTheme();
  const router = useRouter();
  const [spaces, setSpaces] = useState<SpaceRecord[]>([]);

  useEffect(() => {
    if (visible) {
      api.spaces().then(setSpaces).catch(() => setSpaces([]));
    }
  }, [visible]);

  const open = (route: string) => {
    onClose();
    router.push(route as never);
  };

  return (
    <Sheet visible={visible} onClose={onClose}>
      <View style={styles.grid}>
        {FIXED.map((entry) => (
          <Pressable
            key={entry.id}
            onPress={() => open(entry.route)}
            style={[styles.cell, { backgroundColor: colors.surfaceAlt }]}
          >
            <Text style={{ fontSize: 20, color: colors.accent }}>{entry.icon}</Text>
            <Text style={[styles.cellLabel, { color: colors.text }]}>{entry.name}</Text>
          </Pressable>
        ))}
        {spaces.map((entry) => (
          <Pressable
            key={entry.id}
            onPress={() => open(`/space/${entry.id}`)}
            style={[styles.cell, { backgroundColor: colors.surfaceAlt }]}
          >
            <Text style={{ fontSize: 20, color: colors.accent }}>{entry.icon}</Text>
            <Text style={[styles.cellLabel, { color: colors.text }]}>{entry.name}</Text>
            {entry.items > 0 && (
              <Text style={{ color: colors.subtle, fontSize: 9 }}>{entry.items}</Text>
            )}
          </Pressable>
        ))}
      </View>
      <Pressable
        onPress={() => {
          onClose();
          onPrompt('Create a new space for ', false);
        }}
        style={styles.hint}
      >
        <Text style={{ color: colors.subtle, fontSize: typ.small, textAlign: 'center' }}>
          Want another space? Just ask Hermes.
        </Text>
      </Pressable>
    </Sheet>
  );
}

const styles = StyleSheet.create({
  grid: { flexDirection: 'row', flexWrap: 'wrap', gap: sp(3) },
  cell: {
    width: '30.5%',
    borderRadius: radius.md,
    paddingVertical: sp(4),
    alignItems: 'center',
    gap: sp(1.5),
  },
  cellLabel: { fontSize: typ.micro, textAlign: 'center' },
  hint: { marginTop: sp(4) },
});
