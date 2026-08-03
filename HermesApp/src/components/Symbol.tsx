/**
 * Icon = SF Symbol (Apple's native icon system) with graceful fallback.
 *
 * Agent-generated folder icons are SF Symbol names ('airplane',
 * 'banknote', 'graduationcap'); anything that doesn't look like a symbol
 * name (e.g. an emoji from older data) renders as text.
 */
import React from 'react';
import { Text } from 'react-native';
import { SymbolView } from 'expo-symbols';

import { useTheme } from '../theme/useTheme';

const SYMBOL_NAME = /^[a-z0-9]+(\.[a-z0-9]+)*$/;

interface SymbolProps {
  name: string;
  size?: number;
  tint?: string;
  fallback?: string;
}

export function Symbol({ name, size = 18, tint, fallback }: SymbolProps) {
  const { colors } = useTheme();
  const color = tint ?? colors.subtle;

  if (SYMBOL_NAME.test(name)) {
    return (
      <SymbolView
        name={name as never}
        size={size}
        tintColor={color}
        weight="light"
        fallback={<Text style={{ fontSize: size - 2 }}>{fallback ?? '◇'}</Text>}
      />
    );
  }
  return <Text style={{ fontSize: size - 2 }}>{fallback ?? name}</Text>;
}
