/** Generative-UI cards rendered inline when the agent calls show_* tools. */
import React from 'react';
import { Linking, Pressable, StyleSheet, Text, View } from 'react-native';

import type { Card } from '../state/chat';
import { radius, shadow, space, type as typ } from '../theme/tokens';
import { useTheme } from '../theme/useTheme';

function CardShell({ children }: { children: React.ReactNode }) {
  const { colors } = useTheme();
  return (
    <View style={[styles.card, shadow.soft, { backgroundColor: colors.surface, borderColor: colors.hairline }]}>
      {children}
    </View>
  );
}

function Title({ text }: { text: string }) {
  const { colors } = useTheme();
  return <Text style={[styles.title, { color: colors.text }]}>{text}</Text>;
}

function Subtle({ text }: { text: string }) {
  const { colors } = useTheme();
  return <Text style={[styles.subtle, { color: colors.subtle }]}>{text}</Text>;
}

const STATUS_GLYPH: Record<string, string> = { done: '●', in_progress: '◐', pending: '○' };

export function GenCard({ card }: { card: Card }) {
  const { colors } = useTheme();
  const args = card.args as Record<string, any>;

  switch (card.tool) {
    case 'show_plan_card':
      return (
        <CardShell>
          <Title text={String(args.title ?? 'Plan')} />
          {(args.steps ?? []).map((step: any, i: number) => (
            <View key={i} style={styles.row}>
              <Text style={{ color: step.status === 'done' ? colors.success : colors.subtle }}>
                {STATUS_GLYPH[step.status ?? 'pending'] ?? '○'}
              </Text>
              <Text style={[styles.rowText, { color: colors.text }]}>{step.text}</Text>
            </View>
          ))}
        </CardShell>
      );

    case 'show_media_card':
      return (
        <Pressable onPress={() => args.url && Linking.openURL(String(args.url))}>
          <CardShell>
            <View style={styles.mediaRow}>
              <View style={[styles.playBadge, { backgroundColor: colors.accent }]}>
                <Text style={{ color: colors.onAccent, fontSize: 16 }}>▶</Text>
              </View>
              <View style={{ flex: 1 }}>
                <Title text={String(args.title ?? '')} />
                {args.subtitle ? <Subtle text={String(args.subtitle)} /> : null}
              </View>
            </View>
          </CardShell>
        </Pressable>
      );

    case 'show_event_card':
      return (
        <CardShell>
          <Title text={String(args.title ?? 'Event')} />
          <Subtle text={`${args.start ?? ''}${args.end ? ` → ${args.end}` : ''}`} />
          {args.location ? <Subtle text={`📍 ${args.location}`} /> : null}
        </CardShell>
      );

    case 'show_email_draft':
      return (
        <CardShell>
          <Subtle text={`To: ${args.to ?? ''}`} />
          <Title text={String(args.subject ?? '')} />
          <Text style={[styles.body, { color: colors.text }]} numberOfLines={6}>
            {String(args.body ?? '')}
          </Text>
        </CardShell>
      );

    case 'show_chart': {
      const bars: { label: string; value: number }[] = args.bars ?? [];
      const max = Math.max(1, ...bars.map((b) => b.value));
      return (
        <CardShell>
          <Title text={String(args.title ?? 'Chart')} />
          {bars.map((bar, i) => (
            <View key={i} style={styles.barRow}>
              <Text style={[styles.barLabel, { color: colors.subtle }]} numberOfLines={1}>
                {bar.label}
              </Text>
              <View style={[styles.barTrack, { backgroundColor: colors.surfaceAlt }]}>
                <View
                  style={[
                    styles.barFill,
                    { backgroundColor: colors.accent, width: `${(bar.value / max) * 100}%` },
                  ]}
                />
              </View>
              <Text style={[styles.barValue, { color: colors.text }]}>{bar.value}</Text>
            </View>
          ))}
        </CardShell>
      );
    }

    default:
      return null;
  }
}

const styles = StyleSheet.create({
  card: {
    borderRadius: radius.md,
    borderWidth: StyleSheet.hairlineWidth,
    padding: space(4),
    marginTop: space(2),
    gap: space(1),
  },
  title: { fontSize: typ.body, fontWeight: '600' },
  subtle: { fontSize: typ.small },
  body: { fontSize: typ.small, lineHeight: 19, marginTop: space(1) },
  row: { flexDirection: 'row', gap: space(2), alignItems: 'center', marginTop: space(1) },
  rowText: { fontSize: typ.small, flex: 1 },
  mediaRow: { flexDirection: 'row', alignItems: 'center', gap: space(3) },
  playBadge: {
    width: 38,
    height: 38,
    borderRadius: 19,
    alignItems: 'center',
    justifyContent: 'center',
  },
  barRow: { flexDirection: 'row', alignItems: 'center', gap: space(2), marginTop: space(1) },
  barLabel: { fontSize: typ.micro, width: 72 },
  barTrack: { flex: 1, height: 8, borderRadius: 4, overflow: 'hidden' },
  barFill: { height: 8, borderRadius: 4 },
  barValue: { fontSize: typ.micro, width: 40, textAlign: 'right' },
});
