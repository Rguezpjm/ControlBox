import { DashboardShell } from "@/components/layout/dashboard-shell";
import { ProductionBanner } from "@/components/platform/production-banner";

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <DashboardShell banner={<ProductionBanner />}>{children}</DashboardShell>
  );
}
