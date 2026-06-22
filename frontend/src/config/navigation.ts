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
  Blocks,
  Users,
  GitBranch,
  type LucideIcon,
} from "lucide-react";
import type { TranslationKey } from "@/lib/i18n/translations";

export interface NavItem {
  id: string;
  titleKey: TranslationKey;
  href: string;
  icon: LucideIcon;
  badgeKey?: "websites";
  locked?: boolean;
}

export const mainNav: NavItem[] = [
  { id: "dashboard", titleKey: "nav.dashboard", href: "/", icon: LayoutDashboard, locked: true },
  { id: "websites", titleKey: "nav.websites", href: "/websites", icon: Globe, badgeKey: "websites" },
  { id: "wordpress", titleKey: "nav.wordpress", href: "/wordpress", icon: Blocks },
  { id: "staging", titleKey: "nav.staging", href: "/staging", icon: GitBranch },
  { id: "domains", titleKey: "nav.domains", href: "/domains", icon: Link2 },
  { id: "dns", titleKey: "nav.dns", href: "/dns", icon: Server },
  { id: "email", titleKey: "nav.email", href: "/email", icon: Mail },
  { id: "databases", titleKey: "nav.databases", href: "/databases", icon: Database },
  { id: "files", titleKey: "nav.files", href: "/files", icon: Files },
  { id: "ftp", titleKey: "nav.ftp", href: "/ftp", icon: FolderOpen },
  { id: "backups", titleKey: "nav.backups", href: "/backups", icon: Archive },
  { id: "monitoring", titleKey: "nav.monitoring", href: "/monitoring", icon: Activity },
  { id: "security", titleKey: "nav.security", href: "/security", icon: Shield },
  { id: "team", titleKey: "nav.team", href: "/team", icon: Users },
  { id: "settings", titleKey: "nav.settings", href: "/settings", icon: Settings, locked: true },
];

export const databaseEngines = [
  { id: "mysql", name: "MySQL", color: "bg-blue-500" },
  { id: "mariadb", name: "MariaDB", color: "bg-cyan-500" },
  { id: "supabase", name: "Supabase", color: "bg-emerald-500" },
  { id: "mssql", name: "Microsoft SQL", color: "bg-red-500" },
] as const;
