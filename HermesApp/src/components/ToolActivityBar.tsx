/** Quiet chips above the composer while the agent works its tools. */
import React from 'react';
import { ScrollView, StyleSheet, Text, View } from 'react-native';

import { toolLabel } from '../device/frontendTools';
import type { ToolActivity } from '../state/chat';
import { radius, space, type as typ } from '../theme/tokens';
import { useTheme } from '../theme/useTheme';

export function ToolActivityBar({ activity }: { activity: ToolActivity[] }) {
  const { colors } = useTheme();
  const active = activity.filter((a) => !a.done).slice(-3);
  const lastDone = activity.filter((a) => a.done).slice(-1);
  const shown = active.length > 0 ? active : lastDone;
  if (shown.length === 0) return null;

  return (
    <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.row}>
      {shown.map((item) => (
        <View
          key={item.toolCallId}
          style={[styles.chip, { backgroundColor: colors.surfaceAlt, borderColor: colors.hairline }]}
        >
          <Text style={{ color: colors.subtle, fontSize: typ.small }}>
            {item.done ? '✓ ' : '· '}
            {toolLabel(item.name)}
            {item.done ? '' : '…'}
          </Text>
        </View>
      ))}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  row: { gap: space(2), paddingHorizontal: space(4), paddingBottom: space(2) },
  chip: {
    borderRadius: radius.lg,
    borderWidth: StyleSheet.hairlineWidth,
    paddingHorizontal: space(3),
    paddingVertical: space(1.5),
  },
});
