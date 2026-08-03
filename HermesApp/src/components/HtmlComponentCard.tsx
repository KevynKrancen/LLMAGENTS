/**
 * Renders an agent-designed HTML component inline in the chat.
 *
 * The WebView auto-sizes to its content (scrollHeight postMessage) and the
 * app's design tokens are injected as CSS variables, so generated
 * components look native in both light and dark themes.
 */
import React, { useState } from 'react';
import * as Linking from 'expo-linking';
import { Pressable, StyleSheet, Text, View } from 'react-native';
import { WebView } from 'react-native-webview';

import { useChat } from '../state/chat';
import { radius, space, type as typ } from '../theme/tokens';
import { useTheme } from '../theme/useTheme';

const RESHAPE_OPTIONS = ['Simpler', 'More detail', 'As a chart'] as const;

const SIZER = `
  <script>
    const post = () => window.ReactNativeWebView.postMessage(
      String(document.documentElement.scrollHeight));
    window.addEventListener('load', post);
    new ResizeObserver(post).observe(document.documentElement);
  </script>`;

export function HtmlComponentCard({ html }: { html: string }) {
  const { colors, dark } = useTheme();
  const [height, setHeight] = useState(120);
  const [reshapeVisible, setReshapeVisible] = useState(false);

  /** Components are alive: hermes://open opens the phone, hermes://say talks back. */
  const handleAction = (url: string): boolean => {
    if (url.startsWith('hermes://open')) {
      const target = new URL(url).searchParams.get('url');
      if (target) void Linking.openURL(target).catch(() => undefined);
      return false;
    }
    if (url.startsWith('hermes://say')) {
      const text = new URL(url).searchParams.get('text');
      if (text) void useChat.getState().send(text);
      return false;
    }
    return url === 'about:blank' || url.startsWith('data:');
  };

  const document = `<!doctype html><html><head>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
      :root{
        color-scheme:${dark ? 'dark' : 'light'};
        --bg:${colors.bg}; --surface:${colors.surface}; --surface-alt:${colors.surfaceAlt};
        --text:${colors.text}; --subtle:${colors.subtle}; --accent:${colors.accent};
        --hairline:${colors.hairline}; --danger:${colors.danger}; --success:${colors.success};
      }
      *{margin:0;padding:0;box-sizing:border-box}
      body{font-family:-apple-system,system-ui;background:transparent;color:var(--text);
           font-size:14px;line-height:1.5;padding:2px}
    </style></head><body>${html}${SIZER}</body></html>`;

  return (
    <Pressable onLongPress={() => setReshapeVisible((v) => !v)}>
      <View style={[styles.card, { borderColor: colors.hairline, backgroundColor: colors.surface }]}>
        <WebView
          source={{ html: document }}
          style={[styles.web, { height: Math.min(height + 8, 560) }]}
          originWhitelist={['*']}
          scrollEnabled={height > 552}
          onMessage={(event) => {
            const next = Number(event.nativeEvent.data);
            if (Number.isFinite(next) && next > 0) setHeight(next);
          }}
          onShouldStartLoadWithRequest={(request) => handleAction(request.url)}
        />
      </View>
      {reshapeVisible && (
        <View style={styles.reshapeRow}>
          {RESHAPE_OPTIONS.map((option) => (
            <Pressable
              key={option}
              onPress={() => {
                setReshapeVisible(false);
                void useChat.getState().send(`Reshape the last component: ${option.toLowerCase()}.`);
              }}
              style={[styles.reshapeChip, { borderColor: colors.hairline }]}
            >
              <Text style={{ color: colors.subtle, fontSize: typ.micro }}>{option}</Text>
            </Pressable>
          ))}
        </View>
      )}
    </Pressable>
  );
}

const styles = StyleSheet.create({
  card: {
    borderRadius: radius.md,
    borderWidth: StyleSheet.hairlineWidth,
    overflow: 'hidden',
    marginTop: space(2),
  },
  web: { backgroundColor: 'transparent' },
  reshapeRow: { flexDirection: 'row', gap: space(2), marginTop: space(2) },
  reshapeChip: {
    borderWidth: StyleSheet.hairlineWidth,
    borderRadius: radius.lg,
    paddingHorizontal: space(3),
    paddingVertical: space(1.5),
  },
});
