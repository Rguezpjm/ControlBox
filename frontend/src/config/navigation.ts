import {
  LayoutDashboard,
  Globe,
  Link2,
  Server,
  Mail,
  Database,
  FolderOpen,
  Files,
  Archive,
  Activity,
  Shield,
  Settings,
  Layers,
  Blocks,
  Users,
  GitBranch,
  type LucideIcon,
} from "lucide-react";
import type { TranslationKey } from "@/lib/i18n/translations";

export interface NavItem {
  titleKey: TranslationKey;
  href: string;
  icon: LucideIcon;
  badgeKey?: "websites";
}

export const mainNav: NavItem[] = [
  { titleKey: "nav.dashboard", href: "/", icon: LayoutDashboard },
  { titleKey: "nav.websites", href: "/websites", icon: Globe, badgeKey: "websites" },
  { titleKey: "nav.wordpress", href: "/wordpress", icon: Blocks },
  { titleKey: "nav.staging", href: "/staging", icon: GitBranch },
  { titleKey: "nav.domains", href: "/domains", icon: Link2 },
  { titleKey: "nav.dns", href: "/dns", icon: Server },
  { titleKey: "nav.email", href: "/email", icon: Mail },
  { titleKey: "nav.databases", href: "/databases", icon: Database },
  { titleKey: "nav.supabase", href: "/supabase", icon: Layers },
  { titleKey: "nav.files", href: "/files", icon: Files },
  { titleKey: "nav.ftp", href: "/ftp", icon: FolderOpen },
  { titleKey: "nav.backups", href: "/backups", icon: Archive },
  { titleKey: "nav.monitoring", href: "/monitoring", icon: Activity },
  { titleKey: "nav.security", href: "/security", icon: Shield },
  { titleKey: "nav.team", href: "/team", icon: Users },
  { titleKey: "nav.settings", href: "/settings", icon: Settings },
];

export const databaseEngines = [
  { id: "mysql", name: "MySQL", color: "bg-blue-500" },
  { id: "mariadb", name: "MariaDB", color: "bg-cyan-500" },
  { id: "postgresql", name: "PostgreSQL", color: "bg-indigo-500" },
  { id: "mssql", name: "Microsoft SQL", color: "bg-red-500" },
] as const;
