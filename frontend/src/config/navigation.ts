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
  requiredPermissions?: string[];
}

export const mainNav: NavItem[] = [
  { id: "dashboard", titleKey: "nav.dashboard", href: "/", icon: LayoutDashboard, locked: true, requiredPermissions: ["platform.read"] },
  { id: "websites", titleKey: "nav.websites", href: "/websites", icon: Globe, badgeKey: "websites", requiredPermissions: ["websites.read"] },
  { id: "wordpress", titleKey: "nav.wordpress", href: "/wordpress", icon: Blocks, requiredPermissions: ["wordpress.read"] },
  { id: "staging", titleKey: "nav.staging", href: "/staging", icon: GitBranch, requiredPermissions: ["websites.read", "wordpress.read"] },
  { id: "domains", titleKey: "nav.domains", href: "/domains", icon: Link2, requiredPermissions: ["dns.read"] },
  { id: "dns", titleKey: "nav.dns", href: "/dns", icon: Server, requiredPermissions: ["dns.read"] },
  { id: "email", titleKey: "nav.email", href: "/email", icon: Mail, requiredPermissions: ["mail.read"] },
  { id: "databases", titleKey: "nav.databases", href: "/databases", icon: Database, requiredPermissions: ["databases.read"] },
  { id: "files", titleKey: "nav.files", href: "/files", icon: Files, requiredPermissions: ["files.read"] },
  { id: "ftp", titleKey: "nav.ftp", href: "/ftp", icon: FolderOpen, requiredPermissions: ["ftp.read"] },
  { id: "backups", titleKey: "nav.backups", href: "/backups", icon: Archive, requiredPermissions: ["backups.read"] },
  { id: "monitoring", titleKey: "nav.monitoring", href: "/monitoring", icon: Activity, requiredPermissions: ["monitoring.read"] },
  { id: "security", titleKey: "nav.security", href: "/security", icon: Shield, requiredPermissions: ["security.read"] },
  { id: "team", titleKey: "nav.team", href: "/sub-accounts", icon: Users, requiredPermissions: ["team_members.read"] },
  { id: "settings", titleKey: "nav.settings", href: "/settings", icon: Settings, locked: true },
];

export const databaseEngines = [
  { id: "mysql", name: "MySQL", color: "bg-blue-500" },
  { id: "mariadb", name: "MariaDB", color: "bg-cyan-500" },
  { id: "supabase", name: "Supabase", color: "bg-emerald-500" },
  { id: "mssql", name: "Microsoft SQL", color: "bg-red-500" },
] as const;
