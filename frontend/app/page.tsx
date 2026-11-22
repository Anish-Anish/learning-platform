import {
  ActivityIcon,
  ArrowRightIcon,
  CheckIcon,
  FileUpIcon,
  GraduationCapIcon,
  NetworkIcon,
  PresentationIcon,
  ShieldCheckIcon,
  UsersIcon,
} from "lucide-react";
import Link from "next/link";

import { Logo } from "@/components/layout/logo";
import { ThemeToggle } from "@/components/layout/theme-toggle";
import { Button } from "@/components/ui/button";

const ROLES = [
  {
    href: "/play",
    accent: "violet",
    icon: GraduationCapIcon,
    who: "I'm a student",
    cta: "Start learning",
    points: ["Play levels on an adventure map", "Find and fix the real reason you got it wrong", "Teach the bot, beat the boss"],
  },
  {
    href: "/teacher",
    accent: "teal",
    icon: PresentationIcon,
    who: "I'm a teacher",
    cta: "Open my classroom",
    points: ["Turn your PDFs and notes into a course", "See every student's root gaps live", "Get alerts with the reason behind them"],
  },
];

const STEPS = [
  { t: "Answer with confidence", d: "Each answer is marked Sure or Guessing, so a lucky guess and a confident misconception look different." },
  { t: "Trace the root", d: "The tutor walks back through the prerequisites until it finds the concept that actually broke." },
  { t: "Reteach that gap", d: "A short lesson grounded in the teacher's notes, with an analogy and a question that exposes the wrong idea." },
  { t: "Prove it's fixed", d: "A mastery check one level harder, then a boss battle built from the student's own mistakes." },
];

const TEACHER_FLOW = [
  { icon: FileUpIcon, t: "Upload your material", d: "PDFs with tables, diagrams and scanned pages, or Markdown notes." },
  { icon: NetworkIcon, t: "Review what was generated", d: "A concept graph, quizzes with misconception traps, and flashcards. Edit anything." },
  { icon: UsersIcon, t: "Publish and assign", d: "Students see it in their subject switcher; you watch progress on the class overview." },
];

const TRUST = [
  { icon: CheckIcon, t: "AI suggests, code decides", d: "Mastery, XP and unlocks are computed by deterministic, explainable rules." },
  { icon: ShieldCheckIcon, t: "Guardrails everywhere", d: "Grounding checks, injection and PII filtering, moderation, cost limits, and teacher approval." },
  { icon: ActivityIcon, t: "Measured, not claimed", d: "Every request and model call is traced; detection accuracy is tested against simulated students." },
];

export default function Home() {
  return (
    <div data-accent="violet" className="flex min-h-screen flex-col">
      <header className="mx-auto flex w-full max-w-6xl items-center justify-between gap-4 px-4 py-4">
        <Logo />
        <nav className="flex items-center gap-1 text-sm">
          <a href="#how" className="hidden rounded-md px-2.5 py-1.5 text-muted-foreground hover:text-foreground sm:inline">How it works</a>
          <a href="#teachers" className="hidden rounded-md px-2.5 py-1.5 text-muted-foreground hover:text-foreground sm:inline">For teachers</a>
          <ThemeToggle />
        </nav>
      </header>

      <main className="mx-auto w-full max-w-6xl flex-1 px-4">
        {/* 1. What it is + the one decision a visitor has to make */}
        <section className="pt-10 pb-14 text-center sm:pt-16">
          <p className="mx-auto mb-4 w-fit rounded-full border bg-card px-3 py-1 text-xs text-muted-foreground">
            Adaptive AI tutor · AI suggests, code decides
          </p>
          <h1 className="mx-auto max-w-3xl text-4xl font-bold tracking-tight text-balance sm:text-6xl">
            Don&apos;t just find the mistake.{" "}
            <span className="bg-gradient-to-r from-violet-500 to-teal-500 bg-clip-text text-transparent">Fix the root.</span>
          </h1>
          <p className="mx-auto mt-5 max-w-2xl text-lg text-pretty text-muted-foreground">
            Rootwise traces every wrong answer back to the prerequisite gap that caused it, reteaches exactly that, and
            proves it&apos;s fixed.
          </p>

          <div className="mx-auto mt-10 grid max-w-3xl gap-4 text-left sm:grid-cols-2">
            {ROLES.map((r) => (
              <Link key={r.href} href={r.href} data-accent={r.accent}
                className="group flex flex-col rounded-2xl border bg-card p-6 shadow-sm transition-all hover:-translate-y-0.5 hover:border-primary/60 hover:shadow-md">
                <span className="grid size-11 place-items-center rounded-xl bg-primary/10 text-primary">
                  <r.icon className="size-5" />
                </span>
                <p className="mt-4 text-lg font-semibold">{r.who}</p>
                <ul className="mt-2 flex-1 space-y-1.5 text-sm text-muted-foreground">
                  {r.points.map((p) => (
                    <li key={p} className="flex gap-2"><CheckIcon className="mt-0.5 size-4 shrink-0 text-primary" />{p}</li>
                  ))}
                </ul>
                <span className="mt-5 inline-flex items-center gap-1.5 font-medium text-primary">
                  {r.cta} <ArrowRightIcon className="size-4 transition-transform group-hover:translate-x-0.5" />
                </span>
              </Link>
            ))}
          </div>
        </section>

        {/* 2. How the learning loop works */}
        <section id="how" className="scroll-mt-8 py-12">
          <h2 className="text-center text-2xl font-semibold tracking-tight sm:text-3xl">How it works</h2>
          <p className="mx-auto mt-2 max-w-xl text-center text-muted-foreground">One loop, repeated until the gap is gone.</p>
          <ol className="mt-10 grid gap-6 sm:grid-cols-2 lg:grid-cols-4">
            {STEPS.map((s, i) => (
              <li key={s.t} className="relative">
                {i < STEPS.length - 1 && (
                  <span aria-hidden className="absolute top-4 left-10 hidden h-px w-[calc(100%-1rem)] bg-border lg:block" />
                )}
                <span className="relative grid size-8 place-items-center rounded-full bg-primary text-sm font-semibold text-primary-foreground">
                  {i + 1}
                </span>
                <p className="mt-3 font-medium">{s.t}</p>
                <p className="mt-1 text-sm text-muted-foreground">{s.d}</p>
              </li>
            ))}
          </ol>
        </section>

        {/* 3. Teacher workflow */}
        <section id="teachers" data-accent="teal" className="scroll-mt-8 py-12">
          <div className="rounded-3xl border bg-card p-6 sm:p-10">
            <div className="flex flex-wrap items-end justify-between gap-4">
              <div>
                <h2 className="text-2xl font-semibold tracking-tight sm:text-3xl">Your material, turned into a course</h2>
                <p className="mt-2 max-w-xl text-muted-foreground">
                  The teacher studio reads your files and drafts everything. Nothing reaches students until you approve it.
                </p>
              </div>
              <Button asChild>
                <Link href="/teacher/studio">Open the studio <ArrowRightIcon /></Link>
              </Button>
            </div>
            <ol className="mt-8 grid gap-4 md:grid-cols-3">
              {TEACHER_FLOW.map((f, i) => (
                <li key={f.t} className="rounded-2xl border bg-background p-5">
                  <div className="flex items-center gap-2 text-primary">
                    <f.icon className="size-5" />
                    <span className="text-xs font-medium tracking-wide text-muted-foreground uppercase">Step {i + 1}</span>
                  </div>
                  <p className="mt-3 font-medium">{f.t}</p>
                  <p className="mt-1 text-sm text-muted-foreground">{f.d}</p>
                </li>
              ))}
            </ol>
          </div>
        </section>

        {/* 4. Why it can be trusted */}
        <section className="grid gap-6 py-12 sm:grid-cols-3">
          {TRUST.map((f) => (
            <div key={f.t} className="space-y-1.5">
              <f.icon className="size-5 text-primary" />
              <p className="font-medium">{f.t}</p>
              <p className="text-sm text-muted-foreground">{f.d}</p>
            </div>
          ))}
        </section>
      </main>

      <footer className="border-t">
        <div className="mx-auto flex w-full max-w-6xl flex-wrap items-center justify-between gap-3 px-4 py-5 text-sm text-muted-foreground">
          <span>Rootwise · adaptive tutoring that fixes the root</span>
          <nav className="flex gap-4">
            <Link href="/play" className="hover:text-foreground">Student</Link>
            <Link href="/teacher" className="hover:text-foreground">Teacher</Link>
            <Link href="/admin" className="hover:text-foreground">Admin &amp; observability</Link>
          </nav>
        </div>
      </footer>
    </div>
  );
}
