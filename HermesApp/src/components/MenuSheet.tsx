/** The avatar menu — everything that isn't chat lives quietly in here. */
import React from 'react';
import { useRouter } from 'expo-router';
import { Pressable, StyleSheet, Text } from 'react-native';

import { space, type as typ } from '../theme/tokens';
import { useTheme } from '../theme/useTheme';
import { Sheet } from './Sheet';
import { Symbol } from './Symbol';

const ITEMS = [
  { label: 'Artifacts', route: '/artifacts', icon: 'doc.text' },
  { label: 'Routines', route: '/routines', icon: 'arrow.triangle.2.circlepath' },
  { label: 'Connectors', route: '/connectors', icon: 'puzzlepiece.extension' },
  { label: 'Settings', route: '/settings', icon: 'gearshape' },
];

export function MenuSheet({ visible, onClose }: { visible: boolean; onClose: () => void }) {
  const { colors } = useTheme();
  const router = useRouter();

  return (
    <Sheet visible={visible} onClose={onClose}>
      {ITEMS.map((item) => (
        <Pressable
          key={item.route}
          style={[styles.row, { borderBottomColor: colors.hairline }]}
          onPress={() => {
            onClose();
            router.push(item.route as never);
          }}
        >
          <Symbol name={item.icon} size={19} tint={colors.accent} />
          <Text style={{ color: colors.text, fontSize: typ.body }}>{item.label}</Text>
        </Pressable>
      ))}
    </Sheet>
  );
}

const styles = StyleSheet.create({
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: space(3),
    paddingVertical: space(4),
    borderBottomWidth: StyleSheet.hairlineWidth,
  },
});
