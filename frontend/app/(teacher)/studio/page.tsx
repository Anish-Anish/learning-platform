"use client";

import { BookOpenIcon, FileStackIcon, LayersIcon, PlusIcon, SparklesIcon, UsersIcon } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { Dropzone } from "@/components/studio/dropzone";
import { JobProgress, SubjectStatusBadge } from "@/components/studio/status";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { Textarea } from "@/components/ui/textarea";
import { api } from "@/lib/api";
import { useStudioMutation, useSubjects } from "@/lib/queries/studio";
import type { SubjectSummary } from "@/lib/types";

function NewSubjectDialog() {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [files, setFiles] = useState<File[]>([]);
  const create = useStudioMutation(
    () => api.createSubject(name.trim(), description.trim(), files),
    "Upload complete. Generating your subject...",
  );
  return (
    <Dialog open={open} onOpenChange={(o) => !create.isPending && setOpen(o)}>
      <DialogTrigger asChild>
        <Button>
          <PlusIcon /> New subject
        </Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-xl">
        <DialogHeader>
          <DialogTitle>Create a subject from your material</DialogTitle>
          <DialogDescription>
            Rootwise reads your files (text, tables, diagrams and scanned pages), builds the concept graph, and drafts
            notes, quizzes and flashcards. Nothing reaches students until you review and publish.
          </DialogDescription>
        </DialogHeader>
        <div className="grid gap-4">
          <div className="grid gap-2">
            <Label htmlFor="subject-name">Subject name</Label>
            <Input id="subject-name" value={name} maxLength={120} onChange={(e) => setName(e.target.value)} placeholder="e.g. Cell Biology" />
          </div>
          <div className="grid gap-2">
            <Label htmlFor="subject-desc">Description (optional)</Label>
            <Textarea id="subject-desc" value={description} maxLength={1000} rows={2}
              onChange={(e) => setDescription(e.target.value)} placeholder="Who it's for and what it covers" />
          </div>
          <Dropzone files={files} onChange={setFiles} />
        </div>
        <DialogFooter>
          <Button
            disabled={!name.trim() || files.length === 0 || create.isPending}
            onClick={() =>
              create.mutate(undefined, {
                onSuccess: (d) => {
                  setOpen(false);
                  router.push(`/studio/${d.subject.id}`);
                },
              })
            }
          >
            <SparklesIcon /> {create.isPending ? "Uploading..." : "Upload & generate"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function SubjectCard({ s }: { s: SubjectSummary }) {
  return (
    <Link href={`/studio/${s.id}`} className="group">
      <Card className="h-full transition-colors group-hover:border-primary/50">
        <CardHeader>
          <div className="flex items-start justify-between gap-2">
            <CardTitle className="text-base">{s.name}</CardTitle>
            <SubjectStatusBadge status={s.status} />
          </div>
          {s.description && <CardDescription className="line-clamp-2">{s.description}</CardDescription>}
        </CardHeader>
        <CardContent className="space-y-3">
          {s.status === "processing" && s.job ? (
            <JobProgress job={s.job} />
          ) : (
            <div className="grid grid-cols-4 gap-2 text-center text-xs">
              {[
                { icon: LayersIcon, label: "Concepts", v: s.n_concepts },
                { icon: BookOpenIcon, label: "Questions", v: s.n_questions },
                { icon: FileStackIcon, label: "Cards", v: s.n_flashcards },
                { icon: UsersIcon, label: "Students", v: s.n_students },
              ].map((k) => (
                <div key={k.label} className="rounded-lg border p-2">
                  <k.icon className="mx-auto mb-1 size-3.5 text-muted-foreground" />
                  <p className="font-semibold tabular-nums">{k.v}</p>
                  <p className="text-muted-foreground">{k.label}</p>
                </div>
              ))}
            </div>
          )}
          {s.status === "failed" && s.job?.error && <p className="line-clamp-2 text-xs text-destructive">{s.job.error}</p>}
        </CardContent>
      </Card>
    </Link>
  );
}

export default function StudioPage() {
  const subjects = useSubjects();
  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Teacher studio</h1>
          <p className="text-sm text-muted-foreground">
            Upload course material and Rootwise generates the concept graph, quizzes and flashcards. Review, publish,
            then assign the subject to students.
          </p>
        </div>
        <NewSubjectDialog />
      </div>
      {subjects.isLoading ? (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {[0, 1, 2].map((i) => (
            <Skeleton key={i} className="h-48 rounded-xl" />
          ))}
        </div>
      ) : subjects.error ? (
        <p className="text-sm text-destructive">{subjects.error.message}</p>
      ) : (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {subjects.data?.subjects.map((s) => (
            <SubjectCard key={s.id} s={s} />
          ))}
        </div>
      )}
    </div>
  );
}
