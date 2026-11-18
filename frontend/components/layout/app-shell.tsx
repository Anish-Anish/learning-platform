"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { PlayerHud } from "@/components/game/player-hud";
import { Skeleton } from "@/components/ui/skeleton";
import { Button } from "@/components/ui/button";
import { useEnsureStudent } from "@/lib/session-start";
import { useHydrated, useSession } from "@/lib/store";
import { cn } from "@/lib/utils";

import { Logo } from "./logo";
import { StudentSwitcher } from "./student-switcher";
import { SubjectSwitcher } from "./subject-switcher";
import { ThemeToggle } from "./theme-toggle";

type Variant = "student" | "teacher" | "admin";

const NAV: Record<Variant, { href: string; label: string }[]> = {
  student: [
    { href: "/play", label: "🗺️ Adventure" },
    { href: "/learn", label: "⚡ Quick play" },
    { href: "/map", label: "🌳 Skill tree" },
    { href: "/trophies", label: "🏆 Trophies" },
    { href: "/report", label: "📊 Report" },
    { href: "/teach", label: "🤖 Teach" },
  ],
  teacher: [
    { href: "/dashboard", label: "Class dashboard" },
    { href: "/studio", label: "📚 Studio" },
    { href: "/arena", label: "🎮 Game results" },
    { href: "/admin", label: "Admin" },
  ],
  admin: [
    { href: "/admin", label: "Observability" },
    { href: "/dashboard", label: "Teacher" },
  ],
};

const ROLE: Record<Variant, string> = { student: "Student", teacher: "Teacher", admin: "Admin" };

export function AppShell({ variant, children }: { variant: Variant; children: React.ReactNode }) {
  const path = usePathname();
  const storeReady = useHydrated();
  const studentId = useSession((s) => s.studentId);
  const student = useEnsureStudent(studentId, variant === "student" && storeReady);
  // Wait for the persisted store everywhere: requests carry the stored subject id.
  const hydrated = storeReady && (variant !== "student" || student.ready);
  const showSubjects = hydrated && (variant === "student" || (variant === "teacher" && !path.startsWith("/studio")));
  return (
    <div data-accent={variant === "student" ? "violet" : "teal"} className="flex min-h-screen flex-col">
      <header className="sticky top-0 z-40 border-b bg-background/80 backdrop-blur supports-[backdrop-filter]:bg-background/60">
        <div className="mx-auto flex h-14 max-w-7xl items-center gap-4 px-4">
          <Logo />
          <span className="hidden rounded-md bg-primary/10 px-2 py-0.5 text-xs font-medium text-primary sm:inline">
            {ROLE[variant]}
          </span>
          <nav className="ml-2 flex items-center gap-1 overflow-x-auto">
            {NAV[variant].map((n) => (
              <Link
                key={n.href}
                href={n.href}
                className={cn(
                  "rounded-md px-2.5 py-1.5 text-sm whitespace-nowrap text-muted-foreground transition-colors hover:bg-muted hover:text-foreground",
                  path.startsWith(n.href) && "bg-muted font-medium text-foreground",
                )}
              >
                {n.label}
              </Link>
            ))}
          </nav>
          <div className="ml-auto flex items-center gap-1.5">
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
      <main className="mx-auto w-full max-w-7xl flex-1 px-4 py-6">
        {hydrated ? (
          children
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
