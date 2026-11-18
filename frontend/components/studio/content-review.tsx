"use client";

import {
  CheckCircle2Icon,
  CircleAlertIcon,
  PencilIcon,
  PlusIcon,
  RotateCcwIcon,
  ShieldCheckIcon,
  Trash2Icon,
  TriangleAlertIcon,
  XCircleIcon,
} from "lucide-react";
import { useState } from "react";

import { RichText } from "@/components/rich-text";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { Textarea } from "@/components/ui/textarea";
import { api } from "@/lib/api";
import { useStudioConcept, useStudioMutation } from "@/lib/queries/studio";
import type { StudioConcept, StudioFlashcard, StudioQuestion, StudioWorld } from "@/lib/types";
import { cn } from "@/lib/utils";

function EditQuestionDialog({ q, onClose }: { q: StudioQuestion; onClose: () => void }) {
  const [stem, setStem] = useState(q.stem);
  const [explanation, setExplanation] = useState(q.explanation);
  const [options, setOptions] = useState(q.options.map((o) => ({ id: o.id, text: o.text })));
  const save = useStudioMutation(() => api.patchQuestion(q.id, { stem, explanation, options }), "Question saved");
  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle>Edit question</DialogTitle>
          <DialogDescription>Wording only: the correct answer and the misconception behind each trap stay fixed.</DialogDescription>
        </DialogHeader>
        <div className="grid max-h-[60vh] gap-3 overflow-y-auto pr-1">
          <div className="grid gap-1.5">
            <Label htmlFor="q-stem">Question</Label>
            <Textarea id="q-stem" rows={4} value={stem} onChange={(e) => setStem(e.target.value)} />
          </div>
          {q.options.map((o, i) => (
            <div key={o.id} className="grid gap-1.5">
              <Label htmlFor={`q-opt-${o.id}`} className="flex items-center gap-1.5">
                {o.is_correct ? <CheckCircle2Icon className="size-3.5 text-emerald-500" /> : <XCircleIcon className="size-3.5 text-rose-500" />}
                Option {o.id.toUpperCase()} {o.misconception && <span className="font-normal text-muted-foreground">· trap: {o.misconception}</span>}
              </Label>
              <Input id={`q-opt-${o.id}`} value={options[i].text} maxLength={240}
                onChange={(e) => setOptions(options.map((x, j) => (j === i ? { ...x, text: e.target.value } : x)))} />
            </div>
          ))}
          <div className="grid gap-1.5">
            <Label htmlFor="q-exp">Explanation</Label>
            <Textarea id="q-exp" rows={3} value={explanation} onChange={(e) => setExplanation(e.target.value)} />
          </div>
        </div>
        <DialogFooter>
          <Button variant="ghost" onClick={onClose}>Cancel</Button>
          <Button disabled={save.isPending} onClick={() => save.mutate(undefined, { onSuccess: onClose })}>
            {save.isPending ? "Saving..." : "Save"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function QuestionCard({ q, editable, n }: { q: StudioQuestion; editable: boolean; n: number }) {
  const [editing, setEditing] = useState(false);
  const [confirm, setConfirm] = useState(false);
  const remove = useStudioMutation(() => api.deleteQuestion(q.id), "Question deleted");
  return (
    <Card className="gap-3 py-4">
      <CardHeader className="flex flex-row items-center gap-2 space-y-0">
        <span className="text-xs font-medium text-muted-foreground">Q{n}</span>
        <Badge variant="secondary" className="capitalize">{q.bloom_level}</Badge>
        {q.verifier_passed ? (
          <Badge variant="outline" className="gap-1 border-emerald-500/40 text-emerald-700 dark:text-emerald-300">
            <ShieldCheckIcon /> Verified
          </Badge>
        ) : q.verifier_passed === false ? (
          <Badge variant="outline" className="gap-1 border-amber-500/40 text-amber-700 dark:text-amber-300" title={q.verifier_issues.join("; ")}>
            <CircleAlertIcon /> Check
          </Badge>
        ) : null}
        {editable && (
          <div className="ml-auto flex gap-1">
            <Button variant="ghost" size="icon-sm" aria-label="Edit question" onClick={() => setEditing(true)}><PencilIcon /></Button>
            {confirm ? (
              <Button variant="destructive" size="sm" disabled={remove.isPending} onClick={() => remove.mutate(undefined)}>Delete?</Button>
            ) : (
              <Button variant="ghost" size="icon-sm" aria-label="Delete question" onClick={() => setConfirm(true)}><Trash2Icon /></Button>
            )}
          </div>
        )}
      </CardHeader>
      <CardContent className="space-y-2">
        <RichText text={q.stem} className="text-sm" />
        <ul className="space-y-1.5">
          {q.options.map((o) => (
            <li key={o.id} className={cn("rounded-lg border px-3 py-2 text-sm", o.is_correct && "border-emerald-500/50 bg-emerald-500/5")}>
              <div className="flex items-start gap-2">
                {o.is_correct ? <CheckCircle2Icon className="mt-0.5 size-4 shrink-0 text-emerald-500" /> : <span className="mt-0.5 w-4 shrink-0 text-center text-xs text-muted-foreground">{o.id}</span>}
                <span className="flex-1">{o.text}</span>
              </div>
              {o.misconception && <p className="mt-1 pl-6 text-xs text-muted-foreground">Trap: “{o.misconception}”</p>}
            </li>
          ))}
        </ul>
        <p className="text-xs text-muted-foreground"><span className="font-medium text-foreground">Why: </span>{q.explanation}</p>
        {q.verifier_issues.length > 0 && <p className="text-xs text-amber-700 dark:text-amber-300">Verifier: {q.verifier_issues.join("; ")}</p>}
      </CardContent>
      {editing && <EditQuestionDialog q={q} onClose={() => setEditing(false)} />}
    </Card>
  );
}

function Flashcard({ card, editable }: { card: StudioFlashcard; editable: boolean }) {
  const [flipped, setFlipped] = useState(false);
  const [editing, setEditing] = useState(false);
  const [front, setFront] = useState(card.front);
  const [back, setBack] = useState(card.back);
  const save = useStudioMutation(() => api.patchFlashcard(card.id, { front, back }), "Card saved");
  const remove = useStudioMutation(() => api.deleteFlashcard(card.id), "Card deleted");
  if (editing) {
    return (
      <div className="space-y-2 rounded-xl border p-3">
        <Input value={front} maxLength={300} onChange={(e) => setFront(e.target.value)} aria-label="Front" />
        <Textarea value={back} maxLength={600} rows={3} onChange={(e) => setBack(e.target.value)} aria-label="Back" />
        <div className="flex justify-end gap-1">
          <Button variant="ghost" size="sm" onClick={() => setEditing(false)}>Cancel</Button>
          <Button size="sm" disabled={!front.trim() || !back.trim() || save.isPending}
            onClick={() => save.mutate(undefined, { onSuccess: () => setEditing(false) })}>Save</Button>
        </div>
      </div>
    );
  }
  return (
    <div className="group relative">
      <button
        type="button"
        onClick={() => setFlipped(!flipped)}
        className={cn(
          "flex min-h-28 w-full flex-col justify-between rounded-xl border p-3 text-left text-sm transition-colors",
          flipped ? "border-primary/40 bg-primary/5" : "bg-card hover:bg-muted/40",
        )}
      >
        <span className="text-[10px] font-medium tracking-wide text-muted-foreground uppercase">
          {flipped ? "Answer" : "Prompt"} {card.source === "teacher" && "· yours"}
        </span>
        <span className="mt-1">{flipped ? card.back : card.front}</span>
        <RotateCcwIcon className="mt-2 size-3 self-end text-muted-foreground" />
      </button>
      {editable && (
        <div className="absolute top-1.5 right-1.5 flex gap-0.5 opacity-0 transition-opacity group-hover:opacity-100 focus-within:opacity-100">
          <Button variant="ghost" size="icon-xs" aria-label="Edit card" onClick={() => setEditing(true)}><PencilIcon /></Button>
          <Button variant="ghost" size="icon-xs" aria-label="Delete card" disabled={remove.isPending} onClick={() => remove.mutate(undefined)}><Trash2Icon /></Button>
        </div>
      )}
    </div>
  );
}

function AddFlashcard({ conceptId }: { conceptId: string }) {
  const [open, setOpen] = useState(false);
  const [front, setFront] = useState("");
  const [back, setBack] = useState("");
  const add = useStudioMutation(() => api.createFlashcard({ concept_id: conceptId, front, back }), "Card added");
  if (!open) {
    return (
      <button type="button" onClick={() => setOpen(true)}
        className="flex min-h-28 items-center justify-center gap-1.5 rounded-xl border border-dashed text-sm text-muted-foreground hover:border-primary/50 hover:text-foreground">
        <PlusIcon className="size-4" /> Add card
      </button>
    );
  }
  return (
    <div className="space-y-2 rounded-xl border p-3">
      <Input value={front} maxLength={300} placeholder="Prompt" onChange={(e) => setFront(e.target.value)} />
      <Textarea value={back} maxLength={600} rows={2} placeholder="Answer" onChange={(e) => setBack(e.target.value)} />
      <div className="flex justify-end gap-1">
        <Button variant="ghost" size="sm" onClick={() => setOpen(false)}>Cancel</Button>
        <Button size="sm" disabled={!front.trim() || !back.trim() || add.isPending}
          onClick={() => add.mutate(undefined, { onSuccess: () => { setFront(""); setBack(""); setOpen(false); } })}>Add</Button>
      </div>
    </div>
  );
}

function ConceptContent({ conceptId, editable }: { conceptId: string; editable: boolean }) {
  const content = useStudioConcept(conceptId);
  if (content.isLoading) return <Skeleton className="h-96 w-full rounded-xl" />;
  if (!content.data) return <p className="text-sm text-destructive">{content.error?.message}</p>;
  const { concept, questions, flashcards, misconceptions } = content.data;
  return (
    <div className="space-y-5">
      <div>
        <h3 className="text-lg font-semibold">{concept.name}</h3>
        <p className="text-sm text-muted-foreground">{concept.description}</p>
      </div>
      {misconceptions.length > 0 && (
        <div className="rounded-xl border bg-muted/30 p-3">
          <p className="mb-1.5 text-xs font-medium tracking-wide text-muted-foreground uppercase">Misconceptions the traps target</p>
          <ul className="space-y-1 text-sm">
            {misconceptions.map((m) => (
              <li key={m.id}><span className="text-rose-600 dark:text-rose-400">✗ {m.description}</span> <span className="text-muted-foreground">→ {m.correct_belief}</span></li>
            ))}
          </ul>
        </div>
      )}
      <section className="space-y-3">
        <h4 className="text-sm font-medium">Quiz questions ({questions.length})</h4>
        {questions.length === 0 ? (
          <div className="flex items-start gap-2 rounded-xl border border-amber-500/40 bg-amber-500/5 p-3 text-sm">
            <TriangleAlertIcon className="mt-0.5 size-4 shrink-0 text-amber-500" />
            No questions were generated for this concept (the AI was offline or every draft failed verification). Delete
            the concept or regenerate before publishing.
          </div>
        ) : (
          questions.map((q, i) => <QuestionCard key={q.id} q={q} n={i + 1} editable={editable} />)
        )}
      </section>
      <section className="space-y-3">
        <h4 className="text-sm font-medium">Flashcards ({flashcards.length})</h4>
        <div className="grid gap-3 sm:grid-cols-2">
          {flashcards.map((c) => <Flashcard key={c.id} card={c} editable={editable} />)}
          {editable && <AddFlashcard conceptId={concept.id} />}
        </div>
      </section>
    </div>
  );
}

export function ContentReview({ concepts, worlds, editable, selectedId, onSelect }: {
  concepts: StudioConcept[]; worlds: StudioWorld[]; editable: boolean; selectedId: string | null; onSelect: (id: string) => void;
}) {
  const byId = Object.fromEntries(concepts.map((c) => [c.id, c]));
  const groups = worlds.length ? worlds : [{ id: "all", name: "Concepts", emoji: "📘", color: "violet", tagline: "", concepts: concepts.map((c) => c.id) }];
  const current = selectedId && byId[selectedId] ? selectedId : concepts[0]?.id;
  return (
    <div className="grid gap-4 lg:grid-cols-[260px_1fr]">
      <Card className="h-fit py-3">
        <CardHeader className="px-4"><CardTitle className="text-sm">Concepts</CardTitle></CardHeader>
        <CardContent className="max-h-[70vh] space-y-3 overflow-y-auto px-2">
          {groups.map((w) => (
            <div key={w.id}>
              <p className="px-2 pb-1 text-xs font-medium text-muted-foreground">{w.emoji} {w.name}</p>
              {w.concepts.filter((c) => byId[c]).map((cid) => {
                const c = byId[cid];
                return (
                  <button key={cid} type="button" onClick={() => onSelect(cid)}
                    className={cn("flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left text-sm hover:bg-muted",
                      current === cid && "bg-muted font-medium")}>
                    <span className="flex-1 truncate">{c.name}</span>
                    <span className={cn("text-xs tabular-nums", c.n_questions === 0 ? "text-amber-600" : "text-muted-foreground")}>
                      {c.n_questions}Q
                    </span>
                  </button>
                );
              })}
            </div>
          ))}
        </CardContent>
      </Card>
      {current ? <ConceptContent conceptId={current} editable={editable} /> : <p className="text-sm text-muted-foreground">No concepts yet.</p>}
    </div>
  );
}
