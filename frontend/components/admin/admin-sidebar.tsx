"use client";

import {
  ActivityIcon,
  BotIcon,
  GaugeIcon,
  LayoutDashboardIcon,
  ListTreeIcon,
  RadarIcon,
  ScrollTextIcon,
  ShieldCheckIcon,
} from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";

import { LiveToggle, WindowPicker } from "@/components/admin/kit";
import { Badge } from "@/components/ui/badge";
import { useMetrics } from "@/lib/queries/admin";
import { cn } from "@/lib/utils";

export const ADMIN_NAV = [
  { href: "/admin", label: "Overview", icon: LayoutDashboardIcon, exact: true },
  { href: "/admin/requests", label: "Requests", icon: GaugeIcon },
  { href: "/admin/llm", label: "LLM & cost", icon: BotIcon },
  { href: "/admin/traces", label: "Traces", icon: ListTreeIcon },
  { href: "/admin/logs", label: "Logs", icon: ScrollTextIcon },
  { href: "/admin/quality", label: "AI quality", icon: RadarIcon },
  { href: "/admin/guardrails", label: "Guardrails", icon: ShieldCheckIcon },
  { href: "/admin/telemetry", label: "Telemetry", icon: ActivityIcon },
];

export function AdminSidebar() {
  const path = usePathname();
  const metrics = useMetrics();
  const mode = metrics.data?.llm_mode;
  const active = (href: string, exact?: boolean) => (exact ? path === href : path === href || path.startsWith(`${href}/`));
  return (
    <aside className="lg:sticky lg:top-20 lg:h-fit">
      <nav aria-label="Admin sections"
        className="flex gap-1 overflow-x-auto pb-2 lg:flex-col lg:overflow-visible lg:pb-0">
        {ADMIN_NAV.map((n) => (
          <Link
            key={n.href}
            href={n.href}
            aria-current={active(n.href, n.exact) ? "page" : undefined}
            className={cn(
              "flex items-center gap-2 rounded-md px-2.5 py-1.5 text-sm whitespace-nowrap text-muted-foreground transition-colors hover:bg-muted hover:text-foreground",
              active(n.href, n.exact) && "bg-muted font-medium text-foreground",
            )}
          >
            <n.icon className="size-4" /> {n.label}
          </Link>
        ))}
      </nav>
      <div className="mt-4 hidden space-y-2 border-t pt-4 lg:block">
        <p className="text-xs font-medium text-muted-foreground">Time window</p>
        <WindowPicker />
        <LiveToggle />
        {mode && (
          <Badge variant={mode === "online" ? "default" : "secondary"} className="w-full justify-center">
            LLM {mode}
          </Badge>
        )}
      </div>
    </aside>
  );
}

/** Window + live controls for small screens (the sidebar collapses into a tab strip there). */
export function AdminMobileControls() {
  return (
    <div className="grid grid-cols-2 gap-2 lg:hidden">
      <WindowPicker />
      <LiveToggle />
    </div>
  );
}
