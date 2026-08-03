/** Native approval for outbound actions (interrupt_on): approve / reject. */
import * as Haptics from 'expo-haptics';
import React from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';

import { toolLabel } from '../device/frontendTools';
import type { ApprovalRequest } from '../state/chat';
import { radius, space, type as typ } from '../theme/tokens';
import { useTheme } from '../theme/useTheme';
import { Sheet } from './Sheet';

interface ApprovalSheetProps {
  requests: ApprovalRequest[] | null;
  onDecision: (decision: 'approve' | 'reject') => void;
}

export function ApprovalSheet({ requests, onDecision }: ApprovalSheetProps) {
  const { colors } = useTheme();
  if (!requests) return null;

  const decide = (decision: 'approve' | 'reject') => {
    void Haptics.notificationAsync(
      decision === 'approve'
        ? Haptics.NotificationFeedbackType.Success
        : Haptics.NotificationFeedbackType.Warning,
    );
    onDecision(decision);
  };

  return (
    <Sheet visible onClose={() => decide('reject')}>
      <Text style={[styles.heading, { color: colors.text }]}>Hermes wants to…</Text>
      {requests.map((request, i) => (
        <View key={i} style={[styles.request, { backgroundColor: colors.surfaceAlt }]}>
          <Text style={[styles.action, { color: colors.text }]}>{toolLabel(request.action)}</Text>
          {Object.entries(request.args).map(([key, value]) => (
            <Text key={key} style={{ color: colors.subtle, fontSize: typ.small }} numberOfLines={4}>
              {key}: {String(value)}
            </Text>
          ))}
        </View>
      ))}
      <View style={styles.buttons}>
        <Pressable
          onPress={() => decide('reject')}
          style={[styles.button, { backgroundColor: colors.surfaceAlt }]}
        >
          <Text style={{ color: colors.text }}>Not now</Text>
        </Pressable>
        <Pressable
          onPress={() => decide('approve')}
          style={[styles.button, { backgroundColor: colors.accent }]}
        >
          <Text style={{ color: colors.onAccent, fontWeight: '600' }}>Approve</Text>
        </Pressable>
      </View>
    </Sheet>
  );
}

const styles = StyleSheet.create({
  heading: { fontSize: typ.heading, fontWeight: '600', marginBottom: space(3) },
  request: {
    borderRadius: radius.md,
    padding: space(3),
    marginBottom: space(3),
    gap: space(1),
  },
  action: { fontSize: typ.body, fontWeight: '600', textTransform: 'capitalize' },
  buttons: { flexDirection: 'row', gap: space(3), marginTop: space(2) },
  button: {
    flex: 1,
    borderRadius: radius.md,
    paddingVertical: space(3.5),
    alignItems: 'center',
  },
});
