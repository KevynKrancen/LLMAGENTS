import { useColorScheme } from 'react-native';

import { darkPalette, lightPalette, type Theme } from './tokens';

export function useTheme(): Theme {
  const scheme = useColorScheme();
  const dark = scheme === 'dark';
  return { colors: dark ? darkPalette : lightPalette, dark };
}
