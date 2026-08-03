/** Home = the whole app: one serene chat screen, everything else hidden. */
import React, { useRef, useState } from 'react';
import {
  FlatList,
  KeyboardAvoidingView,
  Platform,
  Pressable,
  StyleSheet,
  Text,
  View,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { ApprovalSheet } from '../src/components/ApprovalSheet';
import { CapabilitySheet } from '../src/components/CapabilitySheet';
import { Composer } from '../src/components/Composer';
import { EmptyGreeting } from '../src/components/EmptyGreeting';
import { MenuSheet } from '../src/components/MenuSheet';
import { MessageBubble } from '../src/components/MessageBubble';
import { ModelSheet } from '../src/components/ModelSheet';
import { ThreadDrawer } from '../src/components/ThreadDrawer';
import { Symbol } from '../src/components/Symbol';
import { ToolActivityBar } from '../src/components/ToolActivityBar';
import { useChat } from '../src/state/chat';
import { space, type as typ } from '../src/theme/tokens';
import { useTheme } from '../src/theme/useTheme';

export default function Home() {
  const { colors } = useTheme();
  const chat = useChat();
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);
  const [plusOpen, setPlusOpen] = useState(false);
  const [modelOpen, setModelOpen] = useState(false);
  const [prefill, setPrefill] = useState('');
  const listRef = useRef<FlatList>(null);

  const send = (text: string) => {
    void chat.send(text);
    setTimeout(() => listRef.current?.scrollToEnd({ animated: true }), 80);
  };

  return (
    <SafeAreaView style={[styles.screen, { backgroundColor: colors.bg }]} edges={['top']}>
      {/* Minimal top bar: history · wordmark · menu */}
      <View style={styles.topBar}>
        <Pressable onPress={() => setDrawerOpen(true)} hitSlop={12}>
          <Symbol name="line.3.horizontal" size={20} />
        </Pressable>
        <Text style={[styles.wordmark, { color: colors.text }]}>Hermes</Text>
        <Pressable onPress={() => setMenuOpen(true)} hitSlop={12}>
          <View style={[styles.avatar, { backgroundColor: colors.accent }]}>
            <Text style={{ color: colors.onAccent, fontSize: typ.micro, fontWeight: '600' }}>K</Text>
          </View>
        </Pressable>
      </View>

      <KeyboardAvoidingView
        style={styles.flex}
        behavior={Platform.OS === 'ios' ? 'padding' : undefined}
        keyboardVerticalOffset={0}
      >
        {chat.messages.length === 0 ? (
          <EmptyGreeting onSuggestion={send} />
        ) : (
          <FlatList
            ref={listRef}
            data={chat.messages}
            keyExtractor={(message) => message.id}
            renderItem={({ item }) => <MessageBubble message={item} />}
            contentContainerStyle={styles.list}
            onContentSizeChange={() => listRef.current?.scrollToEnd({ animated: true })}
          />
        )}

        {chat.error && (
          <Text style={[styles.error, { color: colors.danger }]} numberOfLines={2}>
            {chat.error}
          </Text>
        )}
        {chat.running && <ToolActivityBar activity={chat.activity} />}
        <Composer
          onSend={send}
          onPlus={() => setPlusOpen(true)}
          onModelTap={() => setModelOpen(true)}
          running={chat.running}
          onStop={chat.stop}
          prefill={prefill}
          onPrefillConsumed={() => setPrefill('')}
        />
      </KeyboardAvoidingView>

      <ThreadDrawer
        visible={drawerOpen}
        onClose={() => setDrawerOpen(false)}
        onNew={() => {
          chat.newThread();
          setDrawerOpen(false);
        }}
        onPick={(threadId) => {
          void chat.loadThread(threadId);
          setDrawerOpen(false);
        }}
      />
      <MenuSheet visible={menuOpen} onClose={() => setMenuOpen(false)} />
      <CapabilitySheet
        visible={plusOpen}
        onClose={() => setPlusOpen(false)}
        onPrompt={(prompt, autosend) => (autosend ? send(prompt) : setPrefill(prompt))}
      />
      <ModelSheet visible={modelOpen} onClose={() => setModelOpen(false)} />
      <ApprovalSheet requests={chat.interrupt} onDecision={(d) => void chat.resolveInterrupt(d)} />
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1 },
  flex: { flex: 1 },
  topBar: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: space(5),
    paddingVertical: space(2),
  },
  wordmark: { fontSize: typ.body, fontWeight: '600', letterSpacing: 0.5, fontFamily: 'NewYork' },
  avatar: {
    width: 26,
    height: 26,
    borderRadius: 13,
    alignItems: 'center',
    justifyContent: 'center',
  },
  list: { paddingHorizontal: space(4), paddingBottom: space(4) },
  error: { paddingHorizontal: space(5), paddingBottom: space(1), fontSize: typ.small },
});
