import React, { useState } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';

import type { ChatMessage } from '../state/chat';
import { radius, space, type as typ } from '../theme/tokens';
import { useTheme } from '../theme/useTheme';
import { GenCard } from './GenCards';
import { ThemedMarkdown } from './ThemedMarkdown';

export function MessageBubble({ message }: { message: ChatMessage }) {
  const { colors } = useTheme();
  const [showReasoning, setShowReasoning] = useState(false);

  if (message.role === 'user') {
    return (
      <View style={[styles.userBubble, { backgroundColor: colors.bubbleUser }]}>
        <Text style={{ color: colors.text, fontSize: typ.body, lineHeight: 22 }}>{message.text}</Text>
      </View>
    );
  }

  return (
    <View style={styles.assistant}>
      {message.reasoning.length > 0 && (
        <Pressable onPress={() => setShowReasoning((v) => !v)} style={styles.reasoningToggle}>
          <Text style={{ color: colors.subtle, fontSize: typ.small }}>
            {showReasoning ? '▾ thinking' : '▸ thinking'}
          </Text>
        </Pressable>
      )}
      {showReasoning && (
        <View style={[styles.reasoning, { borderColor: colors.hairline }]}>
          <Text style={{ color: colors.subtle, fontSize: typ.small, lineHeight: 19 }}>
            {message.reasoning}
          </Text>
        </View>
      )}
      {message.text.length > 0 && <ThemedMarkdown>{message.text}</ThemedMarkdown>}
      {message.streaming && message.text.length === 0 && (
        <Text style={{ color: colors.subtle, fontSize: typ.body }}>…</Text>
      )}
      {message.cards.map((card, i) => (
        <GenCard key={i} card={card} />
      ))}
    </View>
  );
}

const styles = StyleSheet.create({
  userBubble: {
    alignSelf: 'flex-end',
    maxWidth: '85%',
    borderRadius: radius.lg,
    borderBottomRightRadius: radius.sm,
    paddingHorizontal: space(4),
    paddingVertical: space(2.5),
    marginVertical: space(1.5),
  },
  assistant: { alignSelf: 'stretch', marginVertical: space(1.5) },
  reasoningToggle: { marginBottom: space(1) },
  reasoning: {
    borderLeftWidth: 2,
    paddingLeft: space(3),
    marginBottom: space(2),
  },
});
