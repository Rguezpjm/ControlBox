export type RlsAction = "SELECT" | "INSERT" | "UPDATE" | "DELETE" | "ALL";

export type RlsPreset = {
  id: string;
  label: string;
  policyName: string;
  tableName: string;
  schemaName: string;
  action: RlsAction;
  roleName: string;
  usingExpression: string;
  checkExpression: string | null;
  description: string;
  hint?: string;
};

export const RLS_PRESET_CUSTOM = "custom";

export const RLS_ACTIONS: RlsAction[] = ["SELECT", "INSERT", "UPDATE", "DELETE", "ALL"];

export const RLS_ROLES = [
  { value: "authenticated", label: "Authenticated (logged in)" },
  { value: "anon", label: "Anonymous (public, no login)" },
] as const;

export const RLS_PRESETS: RlsPreset[] = [
  {
    id: "own_rows_full",
    label: "Own data only (read & write)",
    policyName: "users_own_data",
    tableName: "profiles",
    schemaName: "public",
    action: "ALL",
    roleName: "authenticated",
    usingExpression: "auth.uid() = user_id",
    checkExpression: "auth.uid() = user_id",
    description:
      "Logged-in users can only access rows where user_id matches their account.",
    hint: "Table must have a user_id column (UUID) referencing auth.users.",
  },
  {
    id: "own_rows_read",
    label: "Read own rows only",
    policyName: "users_read_own",
    tableName: "profiles",
    schemaName: "public",
    action: "SELECT",
    roleName: "authenticated",
    usingExpression: "auth.uid() = user_id",
    checkExpression: null,
    description: "Users can SELECT only their own rows; writes are blocked unless other policies allow them.",
    hint: "Requires user_id column on the table.",
  },
  {
    id: "public_read",
    label: "Public read (anyone)",
    policyName: "public_read",
    tableName: "posts",
    schemaName: "public",
    action: "SELECT",
    roleName: "anon",
    usingExpression: "true",
    checkExpression: null,
    description: "Anyone can read all rows, even without logging in. Good for public content.",
  },
  {
    id: "authenticated_read_all",
    label: "Logged-in users read all",
    policyName: "auth_read_all",
    tableName: "products",
    schemaName: "public",
    action: "SELECT",
    roleName: "authenticated",
    usingExpression: "true",
    checkExpression: null,
    description: "Any authenticated user can read every row in the table.",
  },
  {
    id: "insert_own",
    label: "Insert own rows only",
    policyName: "insert_own",
    tableName: "todos",
    schemaName: "public",
    action: "INSERT",
    roleName: "authenticated",
    usingExpression: "true",
    checkExpression: "auth.uid() = user_id",
    description: "Users may INSERT rows, but user_id must match their account.",
    hint: "Requires user_id column. Pair with a SELECT/UPDATE policy for full CRUD.",
  },
  {
    id: "update_own",
    label: "Update own rows only",
    policyName: "update_own",
    tableName: "todos",
    schemaName: "public",
    action: "UPDATE",
    roleName: "authenticated",
    usingExpression: "auth.uid() = user_id",
    checkExpression: "auth.uid() = user_id",
    description: "Users can UPDATE only rows they own.",
    hint: "Requires user_id column.",
  },
  {
    id: "delete_own",
    label: "Delete own rows only",
    policyName: "delete_own",
    tableName: "todos",
    schemaName: "public",
    action: "DELETE",
    roleName: "authenticated",
    usingExpression: "auth.uid() = user_id",
    checkExpression: null,
    description: "Users can DELETE only rows where user_id matches their login.",
    hint: "Requires user_id column.",
  },
];

export function getRlsPreset(id: string): RlsPreset | undefined {
  return RLS_PRESETS.find((preset) => preset.id === id);
}

export function applyRlsPreset(presetId: string): {
  presetId: string;
  policyName: string;
  tableName: string;
  schemaName: string;
  action: RlsAction;
  roleName: string;
  usingExpression: string;
  checkExpression: string;
} {
  if (presetId === RLS_PRESET_CUSTOM) {
    return {
      presetId,
      policyName: "",
      tableName: "",
      schemaName: "public",
      action: "ALL",
      roleName: "authenticated",
      usingExpression: "true",
      checkExpression: "",
    };
  }
  const preset = getRlsPreset(presetId);
  return {
    presetId,
    policyName: preset?.policyName ?? "",
    tableName: preset?.tableName ?? "",
    schemaName: preset?.schemaName ?? "public",
    action: preset?.action ?? "ALL",
    roleName: preset?.roleName ?? "authenticated",
    usingExpression: preset?.usingExpression ?? "true",
    checkExpression: preset?.checkExpression ?? "",
  };
}
