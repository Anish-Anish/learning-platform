"use client";

import {
  ArrowLeftIcon,
  CircleAlertIcon,
  EyeOffIcon,
  FilePlus2Icon,
  RefreshCwIcon,
  RocketIcon,
  Trash2Icon,
  TriangleAlertIcon,
} from "lucide-react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useMemo, useState } from "react";

import { StudioConceptGraph, WorldLegend } from "@/components/studio/concept-graph";
import { ConceptSheet } from "@/components/studio/concept-sheet";
import { ContentReview } from "@/components/studio/content-review";
import { Dropzone } from "@/components/studio/dropzone";
import { EnrollmentPanel } from "@/components/studio/enrollment-panel";
import { SourcesTable } from "@/components/studio/sources";
import { JobProgress, SubjectStatusBadge } from "@/components/studio/status";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { api } from "@/lib/api";
import { useStudioGraph, useStudioMutation, useSubject } from "@/lib/queries/studio";

function AddMaterialDialog({ subjectId, open, onOpenChange }: { subjectId: string; open: boolean; onOpenChange: (o: boolean) => void }) {
  const [files, setFiles] = useState<File[]>([]);
  const add = useStudioMutation(() => api.addDocuments(subjectId, files), "Material added. Regenerating...");
  return (
    <Dialog open={open} onOpenChange={(o) => !add.isPending && onOpenChange(o)}>
      <DialogContent className="sm:max-w-xl">
        <DialogHeader>
          <DialogTitle>Add material</DialogTitle>
          <DialogDescription>
            The subject is regenerated from all of its files. Edits you made to the current draft will be replaced.
          </DialogDescription>
        </DialogHeader>
        <Dropzone files={files} onChange={setFiles} />
        <DialogFooter>
          <Button disabled={!files.length || add.isPending}
            onClick={() => add.mutate(undefined, { onSuccess: () => { setFiles([]); onOpenChange(false); } })}>
            {add.isPending ? "Uploading..." : "Upload & regenerate"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

export default function StudioSubjectPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const detail = useSubject(id);
  const status = detail.data?.subject.status;
  const graph = useStudioGraph(id, !!status && status !== "processing");
  const [selected, setSelected] = useState<string | null>(null);
  const [sheetId, setSheetId] = useState<string | null>(null);
  const [tab, setTab] = useState("graph");
  const [adding, setAdding] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);

  const publish = useStudioMutation(() => api.publish(id), "Published! Now assign it to students.");
  const unpublish = useStudioMutation(() => api.unpublish(id), "Unpublished. Students no longer see this subject.");
  const regenerate = useStudioMutation(() => api.regenerate(id), "Regenerating...");
  const remove = useStudioMutation(() => api.deleteSubject(id), "Subject deleted");
  const removeEmpty = useStudioMutation(async (ids: string[]) => {
    for (const cid of ids) await api.deleteConcept(cid);
    return ids.length;
  }, "Removed concepts without questions");

  const concepts = useMemo(() => graph.data?.concepts ?? [], [graph.data]);
  const names = useMemo(() => Object.fromEntries(concepts.map((c) => [c.id, c.name])), [concepts]);
  const emptyIds = concepts.filter((c) => c.n_questions === 0).map((c) => c.id);

  if (detail.isLoading) return <Skeleton className="h-[600px] w-full rounded-xl" />;
  if (!detail.data) {
    return (
      <div className="space-y-3">
        <p className="text-sm text-destructive">{detail.error?.message ?? "Subject not found"}</p>
        <Button variant="outline" asChild><Link href="/studio">Back to studio</Link></Button>
      </div>
    );
  }
  const d = detail.data;
  const s = d.subject;
  const job = s.job;
  const sheetConcept = concepts.find((c) => c.id === sheetId) ?? null;
  const stats = (job?.stats ?? {}) as Record<string, unknown>;

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-start gap-3">
        <Button variant="ghost" size="icon" asChild aria-label="Back to studio">
          <Link href="/studio"><ArrowLeftIcon /></Link>
        </Button>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <h1 className="text-2xl font-semibold tracking-tight">{s.name}</h1>
            <SubjectStatusBadge status={s.status} />
          </div>
          {s.description && <p className="text-sm text-muted-foreground">{s.description}</p>}
          <p className="mt-1 text-xs text-muted-foreground">
            {s.n_concepts} concepts · {s.n_questions} questions · {s.n_flashcards} flashcards · {s.n_documents} files · {s.n_students} students
          </p>
        </div>
        {!s.is_default && (
          <div className="flex flex-wrap gap-2">
            {d.editable && (
              <>
                <Button variant="outline" onClick={() => setAdding(true)}><FilePlus2Icon /> Add material</Button>
                <Button variant="outline" disabled={regenerate.isPending} onClick={() => regenerate.mutate(undefined)}>
                  <RefreshCwIcon /> Regenerate
                </Button>
                <Button
                  disabled={publish.isPending || s.status !== "review" || d.publish_blockers.length > 0}
                  onClick={() => publish.mutate(undefined, { onSuccess: () => setTab("students") })}
                >
                  <RocketIcon /> Publish
                </Button>
              </>
            )}
            {s.status === "published" && (
              <Button variant="outline" disabled={unpublish.isPending} onClick={() => unpublish.mutate(undefined)}>
                <EyeOffIcon /> Unpublish to edit
              </Button>
            )}
            {s.status !== "processing" && (
              <Button variant="ghost" size="icon" aria-label="Delete subject" onClick={() => setConfirmDelete(true)}>
                <Trash2Icon />
              </Button>
            )}
          </div>
        )}
      </div>

      {s.status === "processing" && job && (
        <Card><CardContent><JobProgress job={job} /></CardContent></Card>
      )}

      {s.status === "failed" && (
        <Alert variant="destructive">
          <CircleAlertIcon />
          <AlertTitle>Generation failed</AlertTitle>
          <AlertDescription>{job?.error ?? "Unknown error."} Fix the files or click Regenerate.</AlertDescription>
        </Alert>
      )}

      {s.status === "review" && d.publish_blockers.length > 0 && (
        <Alert>
          <TriangleAlertIcon />
          <AlertTitle>Before you can publish</AlertTitle>
          <AlertDescription>
            <ul className="list-disc pl-4">
              {d.publish_blockers.slice(0, 6).map((b) => <li key={b}>{b}</li>)}
              {d.publish_blockers.length > 6 && <li>and {d.publish_blockers.length - 6} more</li>}
            </ul>
            {emptyIds.length > 0 && emptyIds.length < concepts.length && (
              <Button size="sm" variant="outline" className="mt-2" disabled={removeEmpty.isPending}
                onClick={() => removeEmpty.mutate(emptyIds)}>
                Remove {emptyIds.length} concept{emptyIds.length > 1 ? "s" : ""} without questions
              </Button>
            )}
          </AlertDescription>
        </Alert>
      )}

      {s.status === "review" && d.publish_blockers.length === 0 && (
        <Alert>
          <RocketIcon />
          <AlertTitle>Ready to publish</AlertTitle>
          <AlertDescription>
            Review the graph, quizzes and flashcards, then publish. Assigned students will see it in their subject switcher.
          </AlertDescription>
        </Alert>
      )}

      {d.warnings.length > 0 && s.status !== "processing" && (
        <p className="text-xs text-muted-foreground">Auto-fixes applied: {d.warnings.join(" · ")}</p>
      )}

      {s.status !== "processing" && (
        <Tabs value={tab} onValueChange={setTab}>
          <TabsList>
            <TabsTrigger value="graph">Concept graph</TabsTrigger>
            <TabsTrigger value="content">Quizzes & flashcards</TabsTrigger>
            <TabsTrigger value="students">Students</TabsTrigger>
            <TabsTrigger value="sources">Sources</TabsTrigger>
          </TabsList>
          <TabsContent value="graph" className="space-y-3">
            {graph.isLoading ? (
              <Skeleton className="h-[560px] w-full rounded-xl" />
            ) : concepts.length === 0 ? (
              <p className="text-sm text-muted-foreground">No concepts yet.</p>
            ) : (
              <>
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <WorldLegend worlds={d.worlds} names={names} />
                  <p className="text-xs text-muted-foreground">
                    Click a concept to {d.editable ? "edit its name, prerequisites and notes" : "view it"}. Arrows point from prerequisite to concept.
                  </p>
                </div>
                <StudioConceptGraph concepts={concepts} worlds={d.worlds} selectedId={sheetId}
                  onSelect={(cid) => { setSheetId(cid); setSelected(cid); }} />
              </>
            )}
          </TabsContent>
          <TabsContent value="content">
            <ContentReview concepts={concepts} worlds={d.worlds} editable={d.editable} selectedId={selected} onSelect={setSelected} />
          </TabsContent>
          <TabsContent value="students">
            <EnrollmentPanel subjectId={id} published={s.status === "published"} isDefault={s.is_default} />
          </TabsContent>
          <TabsContent value="sources">
            <SourcesTable documents={d.documents} stats={stats} />
          </TabsContent>
        </Tabs>
      )}

      <ConceptSheet concept={sheetConcept} concepts={concepts} editable={d.editable} onClose={() => setSheetId(null)} />
      <AddMaterialDialog subjectId={id} open={adding} onOpenChange={setAdding} />
      <Dialog open={confirmDelete} onOpenChange={setConfirmDelete}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete “{s.name}”?</DialogTitle>
            <DialogDescription>This removes the subject, its files, quizzes and flashcards. It can&apos;t be undone.</DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="ghost" onClick={() => setConfirmDelete(false)}>Cancel</Button>
            <Button variant="destructive" disabled={remove.isPending}
              onClick={() => remove.mutate(undefined, { onSuccess: () => router.push("/studio") })}>Delete</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
