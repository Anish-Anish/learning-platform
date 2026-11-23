"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Fragment } from "react";

import { PlayerHud } from "@/components/game/player-hud";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { useEnsureStudent } from "@/lib/session-start";
import { useHydrated, useSession } from "@/lib/store";
import { cn } from "@/lib/utils";

import { Logo } from "./logo";
import { RoleSwitcher } from "./role-switcher";
import { StudentSwitcher } from "./student-switcher";
import { SubjectSwitcher } from "./subject-switcher";
import { ThemeToggle } from "./theme-toggle";

export type Variant = "student" | "teacher" | "admin";
type NavItem = { href: string; label: string; exact?: boolean; also?: string[] };

const NAV: Record<Exclude<Variant, "admin">, NavItem[]> = {
  student: [
    { href: "/play", label: "Adventure" },
    { href: "/learn", label: "Quick play" },
    { href: "/map", label: "Skill tree" },
    { href: "/teach", label: "Teach" },
    { href: "/report", label: "Progress" },
    { href: "/trophies", label: "Trophies" },
  ],
  teacher: [
    { href: "/teacher", label: "Class overview", exact: true, also: ["/teacher/students"] },
    { href: "/teacher/studio", label: "Studio" },
    { href: "/teacher/games", label: "Results" },
  ],
};

export function isActive(path: string, item: NavItem) {
  const match = (href: string) => path === href || path.startsWith(`${href}/`);
  return (item.exact ? path === item.href : match(item.href)) || (item.also ?? []).some(match);
}

export function AppShell({ variant, children, wide }: { variant: Variant; children: React.ReactNode; wide?: boolean }) {
  const path = usePathname();
  const storeReady = useHydrated();
  const studentId = useSession((s) => s.studentId);
  const subjectId = useSession((s) => s.subjectId);
  const student = useEnsureStudent(studentId, variant === "student" && storeReady);
  // Wait for the persisted store everywhere: requests carry the stored subject id.
  const hydrated = storeReady && (variant !== "student" || student.ready);
  const showSubjects = hydrated && (variant === "student" || (variant === "teacher" && !path.startsWith("/teacher/studio")));
  const nav = variant === "admin" ? [] : NAV[variant];
  return (
    <div data-accent={variant === "student" ? "violet" : "teal"} className="flex min-h-screen flex-col">
      <header className="sticky top-0 z-40 border-b bg-background/90 backdrop-blur supports-[backdrop-filter]:bg-background/60">
        <div className={cn("mx-auto flex min-h-16 flex-wrap items-center gap-2 px-4 py-2.5 md:flex-nowrap md:gap-3 md:py-2", wide ? "max-w-[1600px]" : "max-w-7xl")}>
          <div className="flex min-w-0 shrink-0 items-center gap-2">
            <Logo />
            <RoleSwitcher current={variant} />
          </div>
          {nav.length > 0 && (
            <nav aria-label={`${variant} navigation`} className="order-3 flex basis-full items-center gap-1 overflow-x-auto rounded-lg border bg-muted/30 p-1.5 md:order-none md:ml-1 md:basis-auto md:border-0 md:bg-transparent md:p-0">
              {nav.map((n) => (
                <Link
                  key={n.href}
                  href={n.href}
                  aria-current={isActive(path, n) ? "page" : undefined}
                  className={cn(
                    "rounded-md px-2.5 py-2 text-xs font-medium whitespace-nowrap text-muted-foreground transition-colors hover:bg-background hover:text-foreground sm:text-sm",
                    isActive(path, n) && "bg-background text-foreground shadow-sm",
                  )}
                >
                  {n.label}
                </Link>
              ))}
            </nav>
          )}
          <div className="ml-auto flex min-w-0 shrink-0 items-center gap-1">
            {showSubjects && <SubjectSwitcher variant={variant === "student" ? "student" : "teacher"} />}
            {variant === "student" && hydrated && (
              <>
                <StudentSwitcher />
                <PlayerHud />
              </>
            )}
            <ThemeToggle />
          </div>
        </div>
      </header>
      <main className={cn("mx-auto w-full flex-1 px-4 py-6", wide ? "max-w-[1600px]" : "max-w-7xl")}>
        {hydrated ? (
          // Remount the page when the subject changes so page-local state (e.g. the current question) resets too.
          <Fragment key={subjectId}>{children}</Fragment>
        ) : student.error ? (
          <div className="mx-auto max-w-md space-y-3 rounded-xl border p-6 text-center">
            <p className="font-medium">Can&apos;t reach the game server</p>
            <p className="text-sm text-muted-foreground">{student.error}</p>
            <Button onClick={() => window.location.reload()}>Retry</Button>
          </div>
        ) : (
          <Skeleton className="h-96 w-full rounded-xl" />
        )}
      </main>
    </div>
  );
}
