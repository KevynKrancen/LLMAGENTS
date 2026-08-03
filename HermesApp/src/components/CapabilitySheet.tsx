/** The hidden depth behind the composer's "+" — quiet capability grid. */
import React from 'react';
import { useRouter } from 'expo-router';
import { Pressable, StyleSheet, Text, View } from 'react-native';

import { radius, space, type as typ } from '../theme/tokens';
import { useTheme } from '../theme/useTheme';
import { Sheet } from './Sheet';

interface Capability {
  icon: string;
  label: string;
  prompt?: string;
  route?: string;
}

const CAPABILITIES: Capability[] = [
  { icon: '▶', label: 'Play on YouTube', prompt: 'Play ' },
  { icon: '☰', label: 'Plan my day', prompt: 'Plan my day around my calendar.' },
  { icon: '✉', label: 'Check email', prompt: 'Anything important in my inbox?' },
  { icon: '◔', label: 'Morning brief', prompt: 'Give me my morning brief.' },
  { icon: '⚡', label: 'Run a shortcut', prompt: 'Run the shortcut ' },
  { icon: '☑', label: 'Remind me', prompt: 'Remind me to ' },
  { icon: '📄', label: 'Artifacts', route: '/artifacts' },
  { icon: '↻', label: 'Routines', route: '/routines' },
];

interface CapabilitySheetProps {
  visible: boolean;
  onClose: () => void;
  onPrompt: (prompt: string, autosend: boolean) => void;
}

export function CapabilitySheet({ visible, onClose, onPrompt }: CapabilitySheetProps) {
  const { colors } = useTheme();
  const router = useRouter();

  const pick = (capability: Capability) => {
    onClose();
    if (capability.route) {
      router.push(capability.route as never);
      return;
    }
    if (capability.prompt) {
      // Prompts ending in a space are prefills; complete sentences send.
      onPrompt(capability.prompt, !capability.prompt.endsWith(' '));
    }
  };

  return (
    <Sheet visible={visible} onClose={onClose}>
      <View style={styles.grid}>
        {CAPABILITIES.map((capability) => (
          <Pressable
            key={capability.label}
            onPress={() => pick(capability)}
            style={[styles.cell, { backgroundColor: colors.surfaceAlt }]}
          >
            <Text style={{ fontSize: 20, color: colors.accent }}>{capability.icon}</Text>
            <Text style={[styles.cellLabel, { color: colors.text }]}>{capability.label}</Text>
          </Pressable>
        ))}
      </View>
    </Sheet>
  );
}

const styles = StyleSheet.create({
  grid: { flexDirection: 'row', flexWrap: 'wrap', gap: space(3) },
  cell: {
    width: '30.5%',
    borderRadius: radius.md,
    paddingVertical: space(4),
    alignItems: 'center',
    gap: space(2),
  },
  cellLabel: { fontSize: typ.micro, textAlign: 'center' },
});
