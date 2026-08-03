/** Push notifications: APNs registration + doorbell handling. */
import * as Notifications from 'expo-notifications';
import { Platform } from 'react-native';

import { api } from '../api/rest';
import { drainDeviceQueue } from './toolExecutor';

Notifications.setNotificationHandler({
  handleNotification: async () => ({
    shouldPlaySound: false,
    shouldSetBadge: false,
    shouldShowBanner: true,
    shouldShowList: true,
  }),
});

/** Register for APNs and send the device token to the backend. */
export async function registerForPush(): Promise<boolean> {
  if (Platform.OS !== 'ios') return false;
  const { status } = await Notifications.requestPermissionsAsync();
  if (status !== 'granted') return false;
  const token = (await Notifications.getDevicePushTokenAsync()).data as string;
  await api.registerDevice(token);
  return true;
}

/** Wire notification listeners; returns an unsubscribe function. */
export function listenForPush(): () => void {
  const onReceive = Notifications.addNotificationReceivedListener((notification) => {
    const data = notification.request.content.data as Record<string, unknown>;
    if (data?.type === 'device_poll') void drainDeviceQueue();
  });
  const onTap = Notifications.addNotificationResponseReceivedListener((response) => {
    const data = response.notification.request.content.data as Record<string, unknown>;
    if (data?.type === 'device_poll' || data?.hermes_command) void drainDeviceQueue();
  });
  return () => {
    onReceive.remove();
    onTap.remove();
  };
}
