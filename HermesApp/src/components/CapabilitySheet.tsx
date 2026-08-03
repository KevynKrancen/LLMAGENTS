/**
 * The ＋ sheet — a window into the agent-shaped workspace.
 *
 * No buttons, no presets. It renders whatever tree the user has grown by
 * talking to Hermes: folders inside folders at any depth, drilled in place.
 * Empty workspace = an invitation, not a template.
 */
import React, { useEffect, useState } from 'react';
import { useRouter } from 'expo-router';
import { Pressable, StyleSheet, Text, View } from 'react-native';

import { api, type WorkspaceNode } from '../api/rest';
import { radius, space as sp, type as typ } from '../theme/tokens';
import { useTheme } from '../theme/useTheme';
import { Sheet } from './Sheet';

interface CapabilitySheetProps {
  visible: boolean;
  onClose: () => void;
  onPrompt: (prompt: string, autosend: boolean) => void;
}

export function CapabilitySheet({ visible, onClose, onPrompt }: CapabilitySheetProps) {
  const { colors } = useTheme();
  const router = useRouter();
  const [tree, setTree] = useState<WorkspaceNode[]>([]);
  // Drill-in path: stack of nodes; the last one's children are displayed.
  const [trail, setTrail] = useState<WorkspaceNode[]>([]);

  useEffect(() => {
    if (visible) {
      setTrail([]);
      api.workspace().then(setTree).catch(() => setTree([]));
    }
  }, [visible]);

  const level = trail.length > 0 ? trail[trail.length - 1]!.children : tree;
  const here = trail[trail.length - 1];

  const enter = (node: WorkspaceNode) => {
    if (node.children.length > 0) {
      setTrail((t) => [...t, node]);
    } else {
      onClose();
      router.push({ pathname: '/space/[id]', params: { id: node.id } } as never);
    }
  };

  return (
    <Sheet visible={visible} onClose={onClose}>
      {/* system surfaces: quiet chips, not part of the tree */}
      <View style={styles.systemRow}>
        {[
          { label: '↻ Routines', route: '/routines' },
          { label: '🧩 Connectors', route: '/connectors' },
        ].map((entry) => (
          <Pressable
            key={entry.route}
            onPress={() => {
              onClose();
              router.push(entry.route as never);
            }}
            style={[styles.systemChip, { borderColor: colors.hairline }]}
          >
            <Text style={{ color: colors.subtle, fontSize: typ.small }}>{entry.label}</Text>
          </Pressable>
        ))}
      </View>

      {trail.length > 0 && (
        <Pressable onPress={() => setTrail((t) => t.slice(0, -1))} style={styles.backRow}>
          <Text style={{ color: colors.accent, fontSize: typ.small }}>
            ‹ {here?.icon} {here?.name}
          </Text>
        </Pressable>
      )}

      {level.length === 0 ? (
        <View style={styles.empty}>
          <Text style={{ color: colors.text, fontSize: typ.body, textAlign: 'center' }}>
            {trail.length === 0 ? 'Your space is unshaped.' : 'Nothing inside yet.'}
          </Text>
          <Text
            style={{ color: colors.subtle, fontSize: typ.small, textAlign: 'center', marginTop: 6 }}
          >
            Tell Hermes what to keep and how to organize it —{'\n'}folders form themselves as you
            speak.
          </Text>
        </View>
      ) : (
        <View style={styles.grid}>
          {level.map((node) => (
            <Pressable
              key={node.id}
              onPress={() => enter(node)}
              onLongPress={() => {
                onClose();
                router.push({ pathname: '/space/[id]', params: { id: node.id } } as never);
              }}
              style={[styles.cell, { backgroundColor: colors.surfaceAlt }]}
            >
              <Text style={{ fontSize: 20 }}>{node.icon}</Text>
              <Text style={[styles.cellLabel, { color: colors.text }]} numberOfLines={1}>
                {node.name}
              </Text>
              <Text style={{ color: colors.subtle, fontSize: 9 }}>
                {node.children.length > 0
                  ? `${node.children.length} ▸`
                  : node.items > 0
                    ? node.items
                    : ''}
              </Text>
            </Pressable>
          ))}
        </View>
      )}

      <Pressable
        onPress={() => {
          onClose();
          onPrompt(
            trail.length > 0 ? `Add a folder inside ${here?.name} for ` : 'Make me a folder for ',
            false,
          );
        }}
        style={styles.hint}
      >
        <Text style={{ color: colors.subtle, fontSize: typ.micro, textAlign: 'center' }}>
          Shape it by asking — "keep this under Travel / Japan"
        </Text>
      </Pressable>
    </Sheet>
  );
}

const styles = StyleSheet.create({
  systemRow: { flexDirection: 'row', gap: sp(2), marginBottom: sp(4) },
  systemChip: {
    borderWidth: StyleSheet.hairlineWidth,
    borderRadius: radius.lg,
    paddingHorizontal: sp(3),
    paddingVertical: sp(1.5),
  },
  backRow: { marginBottom: sp(3) },
  grid: { flexDirection: 'row', flexWrap: 'wrap', gap: sp(3) },
  cell: {
    width: '30.5%',
    borderRadius: radius.md,
    paddingVertical: sp(4),
    alignItems: 'center',
    gap: sp(1),
  },
  cellLabel: { fontSize: typ.micro, textAlign: 'center', paddingHorizontal: 4 },
  empty: { paddingVertical: sp(8) },
  hint: { marginTop: sp(4) },
});
