import { ActivityIcon, ArrowRightIcon, GraduationCapIcon, MicroscopeIcon, PresentationIcon, SwordsIcon } from "lucide-react";
import Link from "next/link";

import { Logo } from "@/components/layout/logo";
import { ThemeToggle } from "@/components/layout/theme-toggle";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

const STEPS = [
  { t: "Answer + confidence", d: "Every answer comes with Sure or Guessing, so a lucky guess and a confident misconception look different." },
  { t: "Trace the root", d: "A diagnosis agent walks the prerequisite graph, probing earlier concepts until it finds the real gap." },
  { t: "Reteach the gap", d: "A streamed micro-lesson grounded in teacher notes, an analogy, and a replay of where your model breaks." },
  { t: "Prove it", d: "Mastery checks one Bloom level higher, then a Root Boss built from your own confident mistakes." },
];

export default function Home() {
  return (
    <div data-accent="violet" className="flex min-h-screen flex-col">
      <header className="mx-auto flex w-full max-w-6xl items-center justify-between px-4 py-4">
        <Logo />
        <ThemeToggle />
      </header>
      <main className="mx-auto w-full max-w-6xl flex-1 px-4">
        <section className="py-14 text-center sm:py-20">
          <p className="mx-auto mb-4 w-fit rounded-full border bg-card px-3 py-1 text-xs text-muted-foreground">
            Adaptive Data Structures tutor · AI suggests, code decides
          </p>
          <h1 className="mx-auto max-w-3xl text-4xl font-bold tracking-tight text-balance sm:text-6xl">
            Don&apos;t just find the mistake.{" "}
            <span className="bg-gradient-to-r from-violet-500 to-teal-500 bg-clip-text text-transparent">Fix the root.</span>
          </h1>
          <p className="mx-auto mt-5 max-w-2xl text-lg text-muted-foreground text-pretty">
            Rootwise traces every wrong answer back to the prerequisite gap that caused it, reteaches exactly that, and
            proves it&apos;s fixed with deterministic, explainable mastery tracking.
          </p>
          <div className="mt-8 flex flex-wrap justify-center gap-3">
            <Button size="lg" asChild>
              <Link href="/play">
                Play the adventure <ArrowRightIcon />
              </Link>
            </Button>
            <Button size="lg" variant="outline" asChild>
              <Link href="/dashboard">Teacher dashboard</Link>
            </Button>
          </div>
        </section>

        <section className="grid gap-3 pb-12 sm:grid-cols-2 lg:grid-cols-4">
          {STEPS.map((s, i) => (
            <Card key={s.t} className="relative">
              <CardHeader>
                <span className="grid size-7 place-items-center rounded-full bg-primary/10 text-sm font-semibold text-primary">{i + 1}</span>
                <CardTitle className="text-base">{s.t}</CardTitle>
                <CardDescription>{s.d}</CardDescription>
              </CardHeader>
            </Card>
          ))}
        </section>

        <section className="grid gap-4 pb-16 md:grid-cols-3">
          {[
            { href: "/play", icon: GraduationCapIcon, title: "Student", body: "Adventure map with levels, hearts, combos and stars, plus boss battles, teach-the-bot and the Root Report.", accent: "violet" },
            { href: "/dashboard", icon: PresentationIcon, title: "Teacher", body: "Live class heatmap, misconception clusters, at-risk alerts, and game results with a leaderboard.", accent: "teal" },
            { href: "/admin", icon: ActivityIcon, title: "Admin / judge", body: "Root-gap detection accuracy, verifier pass rate, latency, cost, guardrail events.", accent: "teal" },
          ].map((c) => (
            <Link key={c.href} href={c.href} data-accent={c.accent} className="group">
              <Card className="h-full transition-colors group-hover:border-primary/60">
                <CardHeader>
                  <c.icon className="size-6 text-primary" />
                  <CardTitle>{c.title}</CardTitle>
                  <CardDescription>{c.body}</CardDescription>
                </CardHeader>
                <CardContent>
                  <span className="inline-flex items-center gap-1 text-sm font-medium text-primary">
                    Open <ArrowRightIcon className="size-4 transition-transform group-hover:translate-x-0.5" />
                  </span>
                </CardContent>
              </Card>
            </Link>
          ))}
        </section>

        <section className="mb-16 grid gap-4 rounded-2xl border bg-card p-6 sm:grid-cols-3">
          {[
            { icon: MicroscopeIcon, t: "Every wrong option is a misconception", d: "73 questions, each distractor tagged with the belief that produces it." },
            { icon: SwordsIcon, t: "Gamified, not gamed", d: "XP only for mastery events. Anti-farming, hints cost XP, bosses built from your own mistakes." },
            { icon: ActivityIcon, t: "Measured", d: "30 simulated students with planted misconceptions prove the diagnosis works." },
          ].map((f) => (
            <div key={f.t} className="space-y-1.5">
              <f.icon className="size-5 text-primary" />
              <p className="font-medium">{f.t}</p>
              <p className="text-sm text-muted-foreground">{f.d}</p>
            </div>
          ))}
        </section>
      </main>
    </div>
  );
}
