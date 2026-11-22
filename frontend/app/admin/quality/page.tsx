"use client";

import { BadgeCheckIcon, BrainIcon, SproutIcon, TargetIcon } from "lucide-react";

import { Empty, ErrorNote, fmt, KV, Loading, PageHeader, Panel, Stat } from "@/components/admin/kit";
import { Badge } from "@/components/ui/badge";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { useMetrics } from "@/lib/queries/admin";

export default function AdminQuality() {
  const metrics = useMetrics();
  const m = metrics.data;
  if (!m) return metrics.error ? <ErrorNote error={metrics.error} /> : <Loading />;
  const q = m.ai_quality;
  const l = m.learning;
  const st = m.studio;
  return (
    <div className="space-y-5">
      <PageHeader title="AI quality & learning"
        description="Does the diagnosis find the real root gap, are generated questions sound, and do students learn?" />
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <Stat icon={SproutIcon} label="Root-gap detection" value={fmt.pct(q.root_gap_detection_exercised)} tone="good"
          sub={q.root_gap_planted ? `of exercised planted misconceptions · ${q.root_gap_detected}/${q.root_gap_planted} overall (${fmt.pct(q.root_gap_detection)})` : "run the class simulator to measure"}
          hint="All-time, against simulator ground truth" />
        <Stat icon={TargetIcon} label="Root concept accuracy" value={fmt.pct(q.root_concept_accuracy)}
          sub="detected misconceptions traced to the right concept (all-time)" />
        <Stat icon={BadgeCheckIcon} label="Verifier first-pass rate" value={fmt.pct(q.verifier_first_pass_rate)}
          sub={q.verifier_first_pass_rate == null ? "no generated questions in this window" : "generated questions accepted on the first try"} />
        <Stat icon={BrainIcon} label="Mastery gain / session" value={fmt.num(l.mastery_gain_per_session, 2)}
          sub={`eval vs control ${typeof l.eval_mastery_gain_vs_control === "number" ? `+${fmt.pct(l.eval_mastery_gain_vs_control)}` : "–"}`} />
      </div>
      <div className="grid gap-5 xl:grid-cols-2">
        <Panel title="Diagnosis & content" description="In the selected window unless marked all-time">
          <KV rows={[
            ["Diagnoses", fmt.int(q.diagnoses_total)],
            ["…by the LLM agent", fmt.int(q.diagnoses_llm)],
            ["…rejected by code", fmt.int(q.diagnoses_rejected), "AI suggests, code decides"],
            ["Grounding failures caught", fmt.int(q.grounding_failures)],
            ["Answer leakage blocked", fmt.int(q.answer_leakage_blocked)],
            ["Teach-scorer agreement (±15)", fmt.pct(q.teach_score_agreement), "from the last eval run"],
            ["Stored questions passing checks", fmt.pct(q.verifier_pass_rate), "all-time; failures are never stored"],
            ["Last eval run", (q.last_eval_at as string) ?? "–"],
          ]} />
        </Panel>
        <Panel title="Learning outcomes">
          <KV rows={[
            ["Answers", fmt.int(l.attempts)],
            ["Active students", fmt.int(l.active_students)],
            ["Accuracy", fmt.pct(l.accuracy)],
            ["Calibration (Sure ↔ correct)", fmt.pct(l.calibration)],
            ["Misconceptions cleared", fmt.int(l.misconceptions_cleared)],
            ["Concepts mastered (all-time)", fmt.int(l.concepts_mastered)],
            ["Avg answers to mastery", fmt.num(l.avg_attempts_to_mastery)],
            ["Session drop-off (<5 answers)", fmt.pct(l.drop_off_rate)],
          ]} />
        </Panel>
      </div>
      <Panel title="Studio generation" description="Teacher material → concept graph, quizzes and flashcards">
        <KV rows={[
          ["Generation jobs", `${fmt.int(st.jobs)} (${fmt.int(st.jobs_failed)} failed, ${fmt.int(st.jobs_running)} running)`],
          ["Job success rate", fmt.pct(st.job_success_rate)],
          ["Job duration avg / p95", `${fmt.secs(st.avg_job_seconds)} / ${fmt.secs(st.p95_job_seconds)}`],
          ["Documents parsed", `${fmt.int(st.documents)} (${fmt.int(st.documents_failed)} failed) · ${fmt.int(st.pages_parsed)} pages`],
          ["Figures described / pages OCR'd", `${fmt.int(st.figures_described)} / ${fmt.int(st.pages_ocr)}`],
          ["Concepts / questions / cards", `${fmt.int(st.concepts_generated)} / ${fmt.int(st.questions_generated)} / ${fmt.int(st.flashcards_generated)}`],
          ["Subjects published / in review", `${fmt.int(st.subjects_published)} / ${fmt.int(st.subjects_in_review)}`],
          ["Studio LLM spend", fmt.usd(st.studio_usd)],
        ]} />
      </Panel>
      <Panel title="Question health"
        description="All-time, current subject. Observed vs model-predicted success; distractors nobody picks are dead weight.">
        {m.question_health.length === 0 ? <Empty>Needs 5+ answers per question.</Empty> : (
          <div className="overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Question</TableHead>
                  <TableHead className="text-right">Answers</TableHead>
                  <TableHead className="text-right">Observed</TableHead>
                  <TableHead className="text-right">Predicted</TableHead>
                  <TableHead>Flag</TableHead>
                  <TableHead>Never-picked options</TableHead>
                  <TableHead className="text-right">Reports</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {m.question_health.map((h) => (
                  <TableRow key={h.question_id}>
                    <TableCell className="font-mono text-xs">{h.question_id}</TableCell>
                    <TableCell className="text-right tabular-nums">{h.attempts}</TableCell>
                    <TableCell className="text-right tabular-nums">{fmt.pct(h.observed_success, 0)}</TableCell>
                    <TableCell className="text-right tabular-nums">{fmt.pct(h.predicted_success, 0)}</TableCell>
                    <TableCell><Badge variant={h.flag === "ok" ? "outline" : "secondary"}>{h.flag.replace("_", " ")}</Badge></TableCell>
                    <TableCell className="text-xs text-muted-foreground">{h.never_picked_options.join(", ") || "–"}</TableCell>
                    <TableCell className="text-right tabular-nums">{h.reports}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        )}
      </Panel>
    </div>
  );
}
