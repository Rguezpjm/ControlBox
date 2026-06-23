export type BucketPreset = {
  id: string;
  label: string;
  name: string;
  public: boolean;
  fileSizeLimitMb: number;
  description: string;
};

export type SchemaPreset = {
  id: string;
  label: string;
  name: string;
  description: string;
};

export const BUCKET_PRESET_CUSTOM = "custom";

export const BUCKET_PRESETS: BucketPreset[] = [
  {
    id: "avatars",
    label: "Avatars — public images",
    name: "avatars",
    public: true,
    fileSizeLimitMb: 5,
    description: "Profile pictures and thumbnails. Public read, authenticated upload.",
  },
  {
    id: "uploads",
    label: "Private uploads",
    name: "uploads",
    public: false,
    fileSizeLimitMb: 50,
    description: "User files that require a signed URL or JWT to access.",
  },
  {
    id: "public-assets",
    label: "Public assets",
    name: "public-assets",
    public: true,
    fileSizeLimitMb: 20,
    description: "Static files: logos, CSS bundles, marketing media.",
  },
  {
    id: "documents",
    label: "Private documents",
    name: "documents",
    public: false,
    fileSizeLimitMb: 100,
    description: "PDFs, invoices, and contracts — never exposed publicly.",
  },
  {
    id: "media",
    label: "Media gallery — public",
    name: "media",
    public: true,
    fileSizeLimitMb: 50,
    description: "Photos and videos for public galleries or CMS content.",
  },
];

export const SCHEMA_PRESET_CUSTOM = "custom";

export const SCHEMA_PRESETS: SchemaPreset[] = [
  {
    id: "app",
    label: "App tables",
    name: "app",
    description: "Application business logic separate from Supabase public schema.",
  },
  {
    id: "private_data",
    label: "Private data",
    name: "private_data",
    description: "Sensitive rows isolated with stricter RLS policies.",
  },
  {
    id: "analytics",
    label: "Analytics & events",
    name: "analytics",
    description: "Event logs, metrics, and reporting tables.",
  },
  {
    id: "integrations",
    label: "Integrations",
    name: "integrations",
    description: "Webhook payloads and third-party sync staging tables.",
  },
];

export function getBucketPreset(id: string): BucketPreset | undefined {
  return BUCKET_PRESETS.find((preset) => preset.id === id);
}

export function getSchemaPreset(id: string): SchemaPreset | undefined {
  return SCHEMA_PRESETS.find((preset) => preset.id === id);
}
