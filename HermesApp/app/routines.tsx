import React, { useCallback, useEffect, useState } from 'react';
import {
  FlatList,
  Pressable,
  RefreshControl,
  StyleSheet,
  Switch,
  Text,
  TextInput,
  View,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { api, type RoutineRecord } from '../src/api/rest';
import { Sheet } from '../src/components/Sheet';
import { radius, space, type as typ } from '../src/theme/tokens';
import { useTheme } from '../src/theme/useTheme';

const CRON_PRESETS = [
  { label: 'Every day · 7:00', cron: '0 7 * * *' },
  { label: 'Weekdays · 8:30', cron: '30 8 * * 1-5' },
  { label: 'Every hour', cron: '0 * * * *' },
  { label: 'Mondays · 9:00', cron: '0 9 * * 1' },
];

export default function Routines() {
  const { colors } = useTheme();
  const [routines, setRoutines] = useState<RoutineRecord[]>([]);
  const [refreshing, setRefreshing] = useState(false);
  const [creating, setCreating] = useState(false);
  const [name, setName] = useState('');
  const [cron, setCron] = useState(CRON_PRESETS[0]!.cron);
  const [prompt, setPrompt] = useState('');
  const [error, setError] = useState('');

  const load = useCallback(() => {
    setRefreshing(true);
    api
      .routines()
      .then((result) => {
        setRoutines(result);
        setError('');
      })
      .catch((e) => setError(String(e.message)))
      .finally(() => setRefreshing(false));
  }, []);

  useEffect(load, [load]);

  const create = async () => {
    if (!name.trim() || !prompt.trim()) return;
    try {
      await api.createRoutine({ name: name.trim(), cron, prompt: prompt.trim() });
      setCreating(false);
      setName('');
      setPrompt('');
      load();
    } catch (e) {
      setError(String((e as Error).message));
    }
  };

  return (
    <SafeAreaView style={[styles.screen, { backgroundColor: colors.bg }]}>
      <View style={styles.header}>
        <Text style={[styles.title, { color: colors.text }]}>Routines</Text>
        <Pressable onPress={() => setCreating(true)} hitSlop={10}>
          <Text style={{ color: colors.accent, fontSize: typ.body }}>＋ New</Text>
        </Pressable>
      </View>
      {error ? (
        <Text style={{ color: colors.danger, paddingHorizontal: space(4) }}>{error}</Text>
      ) : null}
      <FlatList
        data={routines}
        keyExtractor={(routine) => routine.id}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={load} />}
        contentContainerStyle={{ padding: space(4), gap: space(3) }}
        ListEmptyComponent={
          !error ? (
            <Text style={{ color: colors.subtle, textAlign: 'center', marginTop: space(10) }}>
              Routines run Hermes on a schedule — a morning brief,{'\n'}a weekly review — and
              arrive as notifications.
            </Text>
          ) : null
        }
        renderItem={({ item }) => (
          <View
            style={[styles.card, { backgroundColor: colors.surface, borderColor: colors.hairline }]}
          >
            <View style={styles.cardHeader}>
              <Text style={{ color: colors.text, fontSize: typ.body, fontWeight: '600' }}>
                {item.name}
              </Text>
              <Switch
                value={item.enabled}
                onValueChange={(enabled) =>
                  api.toggleRoutine(item.id, enabled).then(load).catch(() => undefined)
                }
                trackColor={{ true: colors.accent }}
              />
            </View>
            <Text style={{ color: colors.subtle, fontSize: typ.micro }}>{item.cron}</Text>
            {item.last_result ? (
              <Text style={{ color: colors.subtle, fontSize: typ.small }} numberOfLines={2}>
                {item.last_result}
              </Text>
            ) : null}
            <Pressable
              onPress={() => api.deleteRoutine(item.id).then(load).catch(() => undefined)}
              hitSlop={8}
            >
              <Text style={{ color: colors.danger, fontSize: typ.micro }}>Delete</Text>
            </Pressable>
          </View>
        )}
      />

      <Sheet visible={creating} onClose={() => setCreating(false)}>
        <Text style={[styles.sheetTitle, { color: colors.text }]}>New routine</Text>
        <TextInput
          style={[styles.input, { color: colors.text, borderColor: colors.hairline }]}
          placeholder="Name (e.g. Morning brief)"
          placeholderTextColor={colors.subtle}
          value={name}
          onChangeText={setName}
        />
        <View style={styles.presets}>
          {CRON_PRESETS.map((preset) => (
            <Pressable
              key={preset.cron}
              onPress={() => setCron(preset.cron)}
              style={[
                styles.preset,
                { backgroundColor: cron === preset.cron ? colors.accent : colors.surfaceAlt },
              ]}
            >
              <Text
                style={{
                  color: cron === preset.cron ? colors.onAccent : colors.text,
                  fontSize: typ.micro,
                }}
              >
                {preset.label}
              </Text>
            </Pressable>
          ))}
        </View>
        <TextInput
          style={[styles.input, { color: colors.text, borderColor: colors.hairline }]}
          value={cron}
          onChangeText={setCron}
          autoCapitalize="none"
          placeholder="cron (min hour dom mon dow)"
          placeholderTextColor={colors.subtle}
        />
        <TextInput
          style={[
            styles.input,
            styles.promptInput,
            { color: colors.text, borderColor: colors.hairline },
          ]}
          placeholder="What should Hermes do each time?"
          placeholderTextColor={colors.subtle}
          value={prompt}
          onChangeText={setPrompt}
          multiline
        />
        <Pressable onPress={create} style={[styles.createButton, { backgroundColor: colors.accent }]}>
          <Text style={{ color: colors.onAccent, fontWeight: '600' }}>Create</Text>
        </Pressable>
      </Sheet>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1 },
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingHorizontal: space(4),
    paddingTop: space(2),
  },
  title: { fontSize: typ.title, fontWeight: '600', fontFamily: 'NewYork' },
  card: {
    borderRadius: radius.md,
    borderWidth: StyleSheet.hairlineWidth,
    padding: space(4),
    gap: space(2),
  },
  cardHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  sheetTitle: { fontSize: typ.heading, fontWeight: '600', marginBottom: space(3) },
  input: {
    borderWidth: StyleSheet.hairlineWidth,
    borderRadius: radius.md,
    padding: space(3),
    fontSize: typ.body,
    marginBottom: space(3),
  },
  promptInput: { minHeight: 80, textAlignVertical: 'top' },
  presets: { flexDirection: 'row', flexWrap: 'wrap', gap: space(2), marginBottom: space(3) },
  preset: { borderRadius: radius.lg, paddingHorizontal: space(3), paddingVertical: space(1.5) },
  createButton: {
    borderRadius: radius.md,
    paddingVertical: space(3.5),
    alignItems: 'center',
  },
});
