import React from 'react';
import Markdown from 'react-native-markdown-display';

import { type as typ } from '../theme/tokens';
import { useTheme } from '../theme/useTheme';

export function ThemedMarkdown({ children }: { children: string }) {
  const { colors } = useTheme();
  return (
    <Markdown
      style={{
        body: { color: colors.text, fontSize: typ.body, lineHeight: 23 },
        paragraph: { marginTop: 0, marginBottom: 8 },
        strong: { fontWeight: '600' },
        link: { color: colors.accent },
        code_inline: {
          backgroundColor: colors.surfaceAlt,
          color: colors.text,
          borderRadius: 4,
          paddingHorizontal: 4,
        },
        code_block: { backgroundColor: colors.surfaceAlt, borderRadius: 10, padding: 10 },
        fence: { backgroundColor: colors.surfaceAlt, borderRadius: 10, padding: 10, borderWidth: 0 },
        bullet_list: { marginBottom: 8 },
        heading1: { fontSize: 22, fontWeight: '600', marginBottom: 8 },
        heading2: { fontSize: 19, fontWeight: '600', marginBottom: 6 },
        heading3: { fontSize: 17, fontWeight: '600', marginBottom: 4 },
        blockquote: {
          backgroundColor: 'transparent',
          borderLeftColor: colors.accent,
          paddingLeft: 10,
        },
        hr: { backgroundColor: colors.hairline },
      }}
    >
      {children}
    </Markdown>
  );
}
