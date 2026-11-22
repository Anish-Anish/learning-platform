import { AdminMobileControls, AdminSidebar } from "@/components/admin/admin-sidebar";
import { AppShell } from "@/components/layout/app-shell";

export default function AdminLayout({ children }: { children: React.ReactNode }) {
  return (
    <AppShell variant="admin" wide>
      <div className="grid gap-6 lg:grid-cols-[200px_minmax(0,1fr)]">
        <AdminSidebar />
        <div className="min-w-0 space-y-5">
          <AdminMobileControls />
          {children}
        </div>
      </div>
    </AppShell>
  );
}
