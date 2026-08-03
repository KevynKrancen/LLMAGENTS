/**
 * Renders an agent-designed HTML component inline in the chat.
 *
 * The WebView auto-sizes to its content (scrollHeight postMessage) and the
 * app's design tokens are injected as CSS variables, so generated
 * components look native in both light and dark themes.
 */
import React, { useState } from 'react';
import { StyleSheet, View } from 'react-native';
import { WebView } from 'react-native-webview';

import { radius, space } from '../theme/tokens';
import { useTheme } from '../theme/useTheme';

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
        // Generated components are display-only: never allow navigation out.
        onShouldStartLoadWithRequest={(request) => request.url === 'about:blank' || request.url.startsWith('data:')}
      />
    </View>
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
});
