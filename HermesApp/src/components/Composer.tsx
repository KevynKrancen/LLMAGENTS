/** Claude-app-style composer: + capability button, model chip, morphing send. */
import * as Haptics from 'expo-haptics';
import React, { useState } from 'react';
import { Pressable, StyleSheet, Text, TextInput, View } from 'react-native';

import { useSettings } from '../state/settings';
import { radius, space, type as typ } from '../theme/tokens';
import { useTheme } from '../theme/useTheme';

interface ComposerProps {
  onSend: (text: string) => void;
  onPlus: () => void;
  onModelTap: () => void;
  running: boolean;
  onStop: () => void;
  /** Text to place in the input (from capability prefills). */
  prefill?: string;
  onPrefillConsumed?: () => void;
}

export function Composer({
  onSend,
  onPlus,
  onModelTap,
  running,
  onStop,
  prefill,
  onPrefillConsumed,
}: ComposerProps) {
  const { colors } = useTheme();
  const [text, setText] = useState('');
  const model = useSettings((s) => s.model);

  React.useEffect(() => {
    if (prefill) {
      setText(prefill);
      onPrefillConsumed?.();
    }
  }, [prefill, onPrefillConsumed]);

  const send = () => {
    const trimmed = text.trim();
    if (!trimmed) return;
    void Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
    setText('');
    onSend(trimmed);
  };

  return (
    <View style={styles.wrap}>
      <Pressable onPress={onModelTap} hitSlop={8} style={styles.modelChip}>
        <Text style={{ color: colors.subtle, fontSize: typ.micro }}>{model} ▾</Text>
      </Pressable>
      <View style={[styles.bar, { backgroundColor: colors.surface, borderColor: colors.hairline }]}>
        <Pressable onPress={onPlus} hitSlop={10} style={styles.plus}>
          <Text style={{ color: colors.subtle, fontSize: 24, lineHeight: 26 }}>＋</Text>
        </Pressable>
        <TextInput
          style={[styles.input, { color: colors.text }]}
          placeholder="Message Hermes"
          placeholderTextColor={colors.subtle}
          value={text}
          onChangeText={setText}
          multiline
          onSubmitEditing={send}
        />
        {running ? (
          <Pressable onPress={onStop} style={[styles.send, { backgroundColor: colors.surfaceAlt }]}>
            <Text style={{ color: colors.text, fontSize: 13 }}>■</Text>
          </Pressable>
        ) : text.trim().length > 0 ? (
          <Pressable onPress={send} style={[styles.send, { backgroundColor: colors.accent }]}>
            <Text style={{ color: colors.onAccent, fontSize: 15 }}>↑</Text>
          </Pressable>
        ) : null}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: { paddingHorizontal: space(4), paddingBottom: space(2) },
  modelChip: { alignSelf: 'center', paddingVertical: space(1) },
  bar: {
    flexDirection: 'row',
    alignItems: 'flex-end',
    borderRadius: radius.lg + 6,
    borderWidth: StyleSheet.hairlineWidth,
    paddingHorizontal: space(3),
    paddingVertical: space(2),
    gap: space(2),
  },
  plus: { paddingBottom: 2 },
  input: { flex: 1, fontSize: typ.body, maxHeight: 120, paddingTop: 4 },
  send: {
    width: 30,
    height: 30,
    borderRadius: 15,
    alignItems: 'center',
    justifyContent: 'center',
  },
});
