"use client";

import { SaveIcon, Trash2Icon } from "lucide-react";
import { useMemo, useState } from "react";

import { RichText } from "@/components/rich-text";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { Textarea } from "@/components/ui/textarea";
import { api } from "@/lib/api";
import { useStudioMutation } from "@/lib/queries/studio";
import type { StudioConcept } from "@/lib/types";

/** Everything that (transitively) depends on `id`: picking one as a prerequisite would make a loop. */
function dependentsOf(id: string, concepts: StudioConcept[]) {
  const out = new Set<string>();
  const stack = [id];
  while (stack.length) {
    const cur = stack.pop()!;
    for (const c of concepts) {
      if (c.prerequisites.includes(cur) && !out.has(c.id)) {
        out.add(c.id);
        stack.push(c.id);
      }
    }
  }
  return out;
}

function Editor({ concept, concepts, editable, onDone }: {
  concept: StudioConcept; concepts: StudioConcept[]; editable: boolean; onDone: () => void;
}) {
  const [name, setName] = useState(concept.name);
  const [description, setDescription] = useState(concept.description);
  const [keyPoints, setKeyPoints] = useState(concept.key_points.join("\n"));
  const [notes, setNotes] = useState(concept.notes_md);
  const [prereqs, setPrereqs] = useState<string[]>(concept.prerequisites);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const blocked = useMemo(() => dependentsOf(concept.id, concepts), [concept.id, concepts]);
  const save = useStudioMutation(
    () => api.patchConcept(concept.id, {
      name: name.trim(), description: description.trim(), notes_md: notes,
      key_points: keyPoints.split("\n").map((k) => k.trim()).filter(Boolean), prerequisites: prereqs,
    }),
    "Concept saved",
  );
  const remove = useStudioMutation(() => api.deleteConcept(concept.id), "Concept removed; its dependents now build on its prerequisites");

  return (
    <div className="space-y-5 pb-8">
      <div className="grid gap-2">
        <Label htmlFor="c-name">Name</Label>
        <Input id="c-name" value={name} disabled={!editable} onChange={(e) => setName(e.target.value)} />
      </div>
      <div className="grid gap-2">
        <Label htmlFor="c-desc">Description</Label>
        <Textarea id="c-desc" rows={2} value={description} disabled={!editable} onChange={(e) => setDescription(e.target.value)} />
      </div>
      <div className="grid gap-2">
        <Label>Prerequisites</Label>
        <p className="text-xs text-muted-foreground">Students unlock this concept after mastering these.</p>
        <div className="max-h-44 space-y-1 overflow-y-auto rounded-lg border p-2">
          {concepts.filter((c) => c.id !== concept.id).map((c) => {
            const loop = blocked.has(c.id);
            return (
              <label key={c.id} className="flex items-center gap-2 text-sm" title={loop ? "Would create a loop" : undefined}>
                <input
                  type="checkbox"
                  className="size-4 accent-[var(--primary)]"
                  disabled={!editable || loop}
                  checked={prereqs.includes(c.id)}
                  onChange={(e) => setPrereqs(e.target.checked ? [...prereqs, c.id] : prereqs.filter((p) => p !== c.id))}
                />
                <span className={loop ? "text-muted-foreground line-through" : ""}>{c.name}</span>
              </label>
            );
          })}
        </div>
      </div>
      <div className="grid gap-2">
        <Label htmlFor="c-kp">Key points (one per line)</Label>
        <Textarea id="c-kp" rows={4} value={keyPoints} disabled={!editable} onChange={(e) => setKeyPoints(e.target.value)} />
      </div>
      <div className="grid gap-2">
        <Label htmlFor="c-notes">Teacher notes</Label>
        <p className="text-xs text-muted-foreground">Lessons, hints and the teach-the-bot scorer are grounded in these notes.</p>
        {editable ? (
          <Textarea id="c-notes" rows={10} value={notes} onChange={(e) => setNotes(e.target.value)} className="font-mono text-xs" />
        ) : (
          <div className="rounded-lg border p-3">
            <RichText text={concept.notes_md} />
          </div>
        )}
      </div>
      {editable && (
        <div className="flex items-center justify-between gap-2">
          {confirmDelete ? (
            <div className="flex items-center gap-2">
              <span className="text-sm">Delete with its quizzes and cards?</span>
              <Button variant="destructive" size="sm" disabled={remove.isPending}
                onClick={() => remove.mutate(undefined, { onSuccess: onDone })}>Delete</Button>
              <Button variant="ghost" size="sm" onClick={() => setConfirmDelete(false)}>Cancel</Button>
            </div>
          ) : (
            <Button variant="ghost" size="sm" className="text-destructive" onClick={() => setConfirmDelete(true)}>
              <Trash2Icon /> Delete concept
            </Button>
          )}
          <Button disabled={save.isPending || !name.trim()} onClick={() => save.mutate(undefined)}>
            <SaveIcon /> {save.isPending ? "Saving..." : "Save"}
          </Button>
        </div>
      )}
    </div>
  );
}

export function ConceptSheet({ concept, concepts, editable, onClose }: {
  concept: StudioConcept | null; concepts: StudioConcept[]; editable: boolean; onClose: () => void;
}) {
  return (
    <Sheet open={!!concept} onOpenChange={(o) => !o && onClose()}>
      <SheetContent className="w-full sm:max-w-lg" data-accent="teal">
        <SheetHeader>
          <SheetTitle>{concept?.name}</SheetTitle>
          <SheetDescription>
            {concept ? `${concept.n_questions} questions · ${concept.n_flashcards} flashcards · ${concept.n_misconceptions} misconceptions` : ""}
          </SheetDescription>
        </SheetHeader>
        <ScrollArea className="h-[calc(100vh-7rem)] px-4">
          {concept && <Editor key={concept.id} concept={concept} concepts={concepts} editable={editable} onDone={onClose} />}
        </ScrollArea>
      </SheetContent>
    </Sheet>
  );
}
