/** Live artifact renderer: html in a WebView, markdown/table/chart natively. */
import React from 'react';
import { ScrollView, StyleSheet, Text, View } from 'react-native';
import { WebView } from 'react-native-webview';

import type { ArtifactRecord } from '../api/rest';
import { radius, space, type as typ } from '../theme/tokens';
import { useTheme } from '../theme/useTheme';
import { ThemedMarkdown } from './ThemedMarkdown';

function parseJson<T>(raw: string): T | null {
  try {
    return JSON.parse(raw) as T;
  } catch {
    return null;
  }
}

export function ArtifactCanvas({ artifact }: { artifact: ArtifactRecord }) {
  const { colors, dark } = useTheme();

  switch (artifact.kind) {
    case 'html': {
      const html = `<!doctype html><html><head><meta name="viewport" content="width=device-width, initial-scale=1">
        <style>:root{color-scheme:${dark ? 'dark' : 'light'};}body{font-family:-apple-system;margin:16px;}</style>
        </head><body>${artifact.content}</body></html>`;
      return <WebView source={{ html }} style={styles.web} originWhitelist={['*']} />;
    }

    case 'markdown':
      return (
        <ScrollView contentContainerStyle={styles.pad}>
          <ThemedMarkdown>{artifact.content}</ThemedMarkdown>
        </ScrollView>
      );

    case 'table': {
      const table = parseJson<{ columns: string[]; rows: (string | number)[][] }>(artifact.content);
      if (!table) return <Fallback text={artifact.content} />;
      return (
        <ScrollView contentContainerStyle={styles.pad} horizontal={false}>
          <View style={[styles.tableHeader, { borderBottomColor: colors.hairline }]}>
            {table.columns.map((column) => (
              <Text key={column} style={[styles.cell, styles.headCell, { color: colors.subtle }]}>
                {column}
              </Text>
            ))}
          </View>
          {table.rows.map((row, i) => (
            <View key={i} style={[styles.tableRow, { borderBottomColor: colors.hairline }]}>
              {row.map((value, j) => (
                <Text key={j} style={[styles.cell, { color: colors.text }]}>
                  {String(value)}
                </Text>
              ))}
            </View>
          ))}
        </ScrollView>
      );
    }

    case 'chart': {
      const chart = parseJson<{
        kind?: string;
        series: { name: string; points: { x: string | number; y: number }[] }[];
      }>(artifact.content);
      if (!chart?.series?.length) return <Fallback text={artifact.content} />;
      const series = chart.series[0]!;
      const max = Math.max(1, ...series.points.map((point) => point.y));
      return (
        <ScrollView contentContainerStyle={styles.pad}>
          <Text style={{ color: colors.subtle, fontSize: typ.small, marginBottom: space(2) }}>
            {series.name}
          </Text>
          {series.points.map((point, i) => (
            <View key={i} style={styles.barRow}>
              <Text style={[styles.barLabel, { color: colors.subtle }]}>{String(point.x)}</Text>
              <View style={[styles.barTrack, { backgroundColor: colors.surfaceAlt }]}>
                <View
                  style={[
                    styles.barFill,
                    { backgroundColor: colors.accent, width: `${(point.y / max) * 100}%` },
                  ]}
                />
              </View>
              <Text style={[styles.barValue, { color: colors.text }]}>{point.y}</Text>
            </View>
          ))}
        </ScrollView>
      );
    }

    default:
      return <Fallback text={artifact.content} />;
  }
}

function Fallback({ text }: { text: string }) {
  const { colors } = useTheme();
  return (
    <ScrollView contentContainerStyle={styles.pad}>
      <Text style={{ color: colors.text, fontSize: typ.small }}>{text}</Text>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  web: { flex: 1, backgroundColor: 'transparent' },
  pad: { padding: space(4) },
  tableHeader: { flexDirection: 'row', borderBottomWidth: 1, paddingBottom: space(2) },
  tableRow: {
    flexDirection: 'row',
    borderBottomWidth: StyleSheet.hairlineWidth,
    paddingVertical: space(2),
  },
  cell: { flex: 1, fontSize: typ.small },
  headCell: { fontWeight: '600' },
  barRow: { flexDirection: 'row', alignItems: 'center', gap: space(2), marginTop: space(1.5) },
  barLabel: { fontSize: typ.micro, width: 76 },
  barTrack: { flex: 1, height: 10, borderRadius: radius.sm / 2, overflow: 'hidden' },
  barFill: { height: 10, borderRadius: radius.sm / 2 },
  barValue: { fontSize: typ.micro, width: 44, textAlign: 'right' },
});
