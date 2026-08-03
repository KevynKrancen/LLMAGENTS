/** The serene empty state: greeting + a few quiet suggestions. */
import React from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';

import { useSettings } from '../state/settings';
import { radius, space, type as typ } from '../theme/tokens';
import { useTheme } from '../theme/useTheme';

const SUGGESTIONS = [
  'Plan my day',
  'Play some music',
  "What's in my inbox?",
  'Morning brief',
];

function greetingForHour(hour: number): string {
  if (hour < 5) return 'Up late';
  if (hour < 12) return 'Good morning';
  if (hour < 18) return 'Good afternoon';
  return 'Good evening';
}

export function EmptyGreeting({ onSuggestion }: { onSuggestion: (text: string) => void }) {
  const { colors } = useTheme();
  const userName = useSettings((s) => s.userName);

  return (
    <View style={styles.wrap}>
      <Text style={[styles.greeting, { color: colors.text }]}>
        {greetingForHour(new Date().getHours())}, {userName}
      </Text>
      <View style={styles.chips}>
        {SUGGESTIONS.map((suggestion) => (
          <Pressable
            key={suggestion}
            onPress={() => onSuggestion(suggestion)}
            style={[styles.chip, { borderColor: colors.hairline, backgroundColor: colors.surface }]}
          >
            <Text style={{ color: colors.subtle, fontSize: typ.small }}>{suggestion}</Text>
          </Pressable>
        ))}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: { flex: 1, alignItems: 'center', justifyContent: 'center', gap: space(6) },
  greeting: {
    fontSize: typ.title,
    fontWeight: '500',
    fontFamily: 'NewYork',
    textAlign: 'center',
  },
  chips: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    justifyContent: 'center',
    gap: space(2),
    paddingHorizontal: space(8),
  },
  chip: {
    borderRadius: radius.lg,
    borderWidth: StyleSheet.hairlineWidth,
    paddingHorizontal: space(4),
    paddingVertical: space(2),
  },
});
