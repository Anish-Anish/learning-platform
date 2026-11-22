"use client";

import { ActivityIcon, GraduationCapIcon, PresentationIcon } from "lucide-react";
import Link from "next/link";

import { cn } from "@/lib/utils";

const ROLES = [
  { id: "student", label: "Student", href: "/play", icon: GraduationCapIcon },
  { id: "teacher", label: "Teacher", href: "/teacher", icon: PresentationIcon },
  { id: "admin", label: "Admin", href: "/admin", icon: ActivityIcon },
] as const;

/** One consistent way to move between the three apps (replaces cross-links inside each nav). */
export function RoleSwitcher({ current }: { current: "student" | "teacher" | "admin" }) {
  return (
    <div role="navigation" aria-label="Switch role" className="hidden items-center rounded-lg border bg-muted/40 p-0.5 md:flex">
      {ROLES.map((r) => {
        const active = r.id === current;
        return (
          <Link
            key={r.id}
            href={r.href}
            aria-current={active ? "page" : undefined}
            title={`${r.label} view`}
            className={cn(
              "flex items-center gap-1 rounded-md px-2 py-1 text-xs font-medium transition-colors",
              active ? "bg-background text-primary shadow-xs" : "text-muted-foreground hover:text-foreground",
            )}
          >
            <r.icon className="size-3.5" />
            <span className={cn(!active && "hidden xl:inline")}>{r.label}</span>
          </Link>
        );
      })}
    </div>
  );
}
