/** Provider + model picker, reachable from the composer chip and Settings. */
import React from 'react';
import { Pressable, StyleSheet, Text, TextInput, View } from 'react-native';

import { PROVIDERS, useSettings, type Provider } from '../state/settings';
import { radius, space, type as typ } from '../theme/tokens';
import { useTheme } from '../theme/useTheme';
import { Sheet } from './Sheet';

export function ModelSheet({ visible, onClose }: { visible: boolean; onClose: () => void }) {
  const { colors } = useTheme();
  const { provider, model, setModel } = useSettings();

  const pickProvider = (next: Provider) => {
    const preset = PROVIDERS.find((p) => p.key === next);
    setModel(next, preset?.defaultModel ?? model);
  };

  return (
    <Sheet visible={visible} onClose={onClose}>
      <Text style={[styles.heading, { color: colors.text }]}>Model</Text>
      <View style={styles.providers}>
        {PROVIDERS.map((entry) => (
          <Pressable
            key={entry.key}
            onPress={() => pickProvider(entry.key)}
            style={[
              styles.provider,
              {
                backgroundColor: provider === entry.key ? colors.accent : colors.surfaceAlt,
              },
            ]}
          >
            <Text
              style={{
                color: provider === entry.key ? colors.onAccent : colors.text,
                fontSize: typ.small,
              }}
            >
              {entry.label}
            </Text>
          </Pressable>
        ))}
      </View>
      <TextInput
        style={[styles.input, { color: colors.text, borderColor: colors.hairline }]}
        value={model}
        onChangeText={(next) => setModel(provider, next)}
        autoCapitalize="none"
        autoCorrect={false}
        placeholder="model id"
        placeholderTextColor={colors.subtle}
      />
      <Text style={{ color: colors.subtle, fontSize: typ.micro, marginTop: space(2) }}>
        Applied on your next message — no restart needed.
      </Text>
    </Sheet>
  );
}

const styles = StyleSheet.create({
  heading: { fontSize: typ.heading, fontWeight: '600', marginBottom: space(4) },
  providers: { flexDirection: 'row', flexWrap: 'wrap', gap: space(2), marginBottom: space(4) },
  provider: {
    borderRadius: radius.lg,
    paddingHorizontal: space(4),
    paddingVertical: space(2),
  },
  input: {
    borderWidth: StyleSheet.hairlineWidth,
    borderRadius: radius.md,
    padding: space(3),
    fontSize: typ.body,
  },
});
