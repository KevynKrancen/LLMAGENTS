import React, { useEffect } from 'react';
import * as Linking from 'expo-linking';
import { Stack } from 'expo-router';
import { StatusBar } from 'expo-status-bar';

import { handleIncomingUrl } from '../src/device/toolExecutor';
import { listenForPush } from '../src/device/push';
import { useTheme } from '../src/theme/useTheme';

export default function RootLayout() {
  const { colors, dark } = useTheme();

  useEffect(() => {
    const urlSub = Linking.addEventListener('url', ({ url }) => handleIncomingUrl(url));
    const unlistenPush = listenForPush();
    return () => {
      urlSub.remove();
      unlistenPush();
    };
  }, []);

  return (
    <>
      <StatusBar style={dark ? 'light' : 'dark'} />
      <Stack
        screenOptions={{
          headerShown: false,
          contentStyle: { backgroundColor: colors.bg },
        }}
      >
        <Stack.Screen name="index" />
        <Stack.Screen name="artifacts" options={{ presentation: 'modal' }} />
        <Stack.Screen name="artifact/[id]" />
        <Stack.Screen name="routines" options={{ presentation: 'modal' }} />
        <Stack.Screen name="settings" options={{ presentation: 'modal' }} />
      </Stack>
    </>
  );
}
