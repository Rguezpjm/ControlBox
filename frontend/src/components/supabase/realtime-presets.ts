export type RealtimePreset = {
  id: string;
  label: string;
  channelName: string;
  tableName: string;
  schemaName: string;
  description: string;
  events: string[];
};

export const REALTIME_PRESET_CUSTOM = "custom";

export const REALTIME_PRESETS: RealtimePreset[] = [
  {
    id: "chat_messages",
    label: "Chat / messages",
    channelName: "messages",
    tableName: "messages",
    schemaName: "public",
    description:
      "Broadcast new and updated chat messages to connected clients (requires a messages table).",
    events: ["INSERT", "UPDATE"],
  },
  {
    id: "notifications",
    label: "In-app notifications",
    channelName: "notifications",
    tableName: "notifications",
    schemaName: "public",
    description: "Push notification rows to the UI when INSERT or UPDATE occurs.",
    events: ["INSERT", "UPDATE"],
  },
  {
    id: "todo_sync",
    label: "Todo / task lists",
    channelName: "todos",
    tableName: "todos",
    schemaName: "public",
    description: "Keep task lists in sync across tabs and devices.",
    events: ["INSERT", "UPDATE", "DELETE"],
  },
  {
    id: "user_profiles",
    label: "User profiles",
    channelName: "profiles",
    tableName: "profiles",
    schemaName: "public",
    description: "Live profile updates (avatar, display name, status).",
    events: ["UPDATE"],
  },
  {
    id: "order_status",
    label: "Order status",
    channelName: "orders",
    tableName: "orders",
    schemaName: "public",
    description: "E-commerce or booking status changes streamed to dashboards.",
    events: ["UPDATE"],
  },
  {
    id: "presence",
    label: "Presence / activity feed",
    channelName: "activity",
    tableName: "activity_log",
    schemaName: "public",
    description: "Activity feed or audit log entries as they are created.",
    events: ["INSERT"],
  },
];

export function getRealtimePreset(id: string): RealtimePreset | undefined {
  return REALTIME_PRESETS.find((preset) => preset.id === id);
}

export function applyRealtimePreset(presetId: string): {
  presetId: string;
  channelName: string;
  tableName: string;
  schemaName: string;
} {
  if (presetId === REALTIME_PRESET_CUSTOM) {
    return { presetId, channelName: "", tableName: "", schemaName: "public" };
  }
  const preset = getRealtimePreset(presetId);
  return {
    presetId,
    channelName: preset?.channelName ?? "",
    tableName: preset?.tableName ?? "",
    schemaName: preset?.schemaName ?? "public",
  };
}
