"use client";

import { CoinsIcon, FileWarningIcon, MessageSquareWarningIcon, ShieldCheckIcon } from "lucide-react";

import { ErrorNote, fmt, Loading, PageHeader, Panel, Stat } from "@/components/admin/kit";
import { useMetrics } from "@/lib/queries/admin";
import { cn } from "@/lib/utils";

type Row = { name: string; what: string; count: number | null };

function GuardTable({ rows }: { rows: Row[] }) {
  return (
    <ul className="divide-y text-sm">
      {rows.map((r) => (
        <li key={r.name} className="flex items-start gap-3 py-2">
          <div className="flex-1">
            <p className="font-medium">{r.name}</p>
            <p className="text-xs text-muted-foreground">{r.what}</p>
          </div>
          <span className={cn("min-w-10 text-right font-semibold tabular-nums", r.count ? "text-amber-600 dark:text-amber-400" : "text-muted-foreground")}>
            {r.count == null ? "always on" : fmt.int(r.count)}
          </span>
        </li>
      ))}
    </ul>
  );
}

export default function AdminGuardrails() {
  const metrics = useMetrics();
  const m = metrics.data;
  if (!m) return metrics.error ? <ErrorNote error={metrics.error} /> : <Loading />;
  const s = m.safety;
  return (
    <div className="space-y-5">
      <PageHeader title="Guardrails"
        description="What each guard does and how often it fired in the selected window. Counts come from llm_calls flags, request status codes and studio job reports." />
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <Stat icon={MessageSquareWarningIcon} label="Prompt injections neutralised" value={fmt.int(s.injection_attempts + s.document_injection_suspects)}
          sub={`${s.injection_attempts} in student text · ${s.document_injection_suspects} in uploaded documents`} />
        <Stat icon={ShieldCheckIcon} label="Blocked by moderation" value={fmt.int(s.blocked_calls)} sub={`${s.moderation_flags} moderation flags in total`} />
        <Stat icon={FileWarningIcon} label="Generated content dropped" value={fmt.int(s.output_guardrail_drops)}
          sub={`${s.studio_moderation_flags} concepts flagged for teacher review`} />
        <Stat icon={CoinsIcon} label="Cost guards tripped" value={fmt.int(s.rate_limited + s.budget_exceeded + s.job_budget_exceeded + s.uploads_rejected)}
          sub={`${s.rate_limited} rate-limited · ${s.budget_exceeded + s.job_budget_exceeded} budget · ${s.uploads_rejected} uploads`} />
      </div>
      <div className="grid gap-5 xl:grid-cols-2">
        <Panel title="Input" description="Before anything reaches a model">
          <GuardTable rows={[
            { name: "Prompt-injection detection", what: "Student and document text is wrapped in data delimiters; instruction-like text is flagged and never followed.", count: s.injection_attempts + s.document_injection_suspects },
            { name: "Moderation", what: "OpenAI moderation (local list offline). Flagged student text never reaches the model; a safe fallback answers.", count: s.blocked_calls },
            { name: "PII scrubbing", what: "Emails, phone numbers and links with parameters are removed from prompts and logs. Students are pseudonymous.", count: s.pii_scrubbed },
            { name: "Length limits", what: "Free text is truncated; uploaded documents are capped per field.", count: null },
            { name: "Off-topic redirects", what: "Teach-the-bot steers back to the concept instead of chatting.", count: s.off_topic_redirects },
          ]} />
        </Panel>
        <Panel title="Output" description="Before anything reaches a student">
          <GuardTable rows={[
            { name: "Structured output + schema validation", what: "Every call is parsed into a schema; one retry, then a deterministic fallback.", count: null },
            { name: "Grounding checks", what: "Lessons and generated notes must use the teacher notes / source material; otherwise retried or replaced.", count: m.ai_quality.grounding_failures as number },
            { name: "Answer-leakage block", what: "Hints and lessons may not reveal the answer to a pending question.", count: m.ai_quality.answer_leakage_blocked as number },
            { name: "Generated-content screening", what: "Studio cards/questions with injected instructions or no grounding are dropped; tone is softened.", count: s.output_guardrail_drops },
            { name: "Code decides", what: "Diagnoses are validated by code (real concept/misconception ids) before they change any state.", count: m.ai_quality.diagnoses_rejected as number },
          ]} />
        </Panel>
        <Panel title="Cost & abuse">
          <GuardTable rows={[
            { name: "Per-student daily token budget", what: "Over budget, learner features switch to fallbacks.", count: s.budget_exceeded },
            { name: "Per-job token budget (studio)", what: "A generation job stops calling the model once STUDIO_MAX_TOKENS_PER_JOB is used.", count: s.job_budget_exceeded },
            { name: "Rate limits", what: "Teach, hints, lessons per student; studio generation per client. Returns 429 with Retry-After.", count: s.rate_limited },
            { name: "Upload limits", what: "Type and magic-byte checks, size per file, and oversized requests rejected before they are read.", count: s.uploads_rejected },
          ]} />
        </Panel>
        <Panel title="Request hygiene">
          <GuardTable rows={[
            { name: "Trace-id sanitising", what: "Client-supplied trace ids must be short and alphanumeric, or a new one is issued (no log injection).", count: null },
            { name: "Security headers", what: "nosniff, frame DENY, no-referrer and no-store on every API response.", count: null },
            { name: "Human in the loop", what: "Nothing generated in the studio reaches students until a teacher reviews and publishes it.", count: null },
          ]} />
        </Panel>
      </div>
    </div>
  );
}
