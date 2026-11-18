"use client";

import { SaveIcon, UserPlusIcon } from "lucide-react";
import { useMemo, useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { api } from "@/lib/api";
import { useEnrollment, useStudioMutation } from "@/lib/queries/studio";

const VALID = /^[A-Za-z0-9_-]{1,64}$/;

export function EnrollmentPanel({ subjectId, published, isDefault }: { subjectId: string; published: boolean; isDefault: boolean }) {
  const list = useEnrollment(subjectId);
  const saved = useMemo(() => new Set(list.data?.students.filter((s) => s.enrolled).map((s) => s.id) ?? []), [list.data]);
  const [draft, setDraft] = useState<Set<string> | null>(null);
  const selected = draft ?? saved;
  const setSelected = setDraft;
  const [extra, setExtra] = useState<string[]>([]);
  const [newId, setNewId] = useState("");
  const [filter, setFilter] = useState("");

  const rows = useMemo(() => {
    const known = list.data?.students ?? [];
    const added = extra.filter((id) => !known.some((s) => s.id === id)).map((id) => ({ id, display_name: "New student", is_simulated: false, enrolled: false }));
    const q = filter.trim().toLowerCase();
    return [...added, ...known].filter((s) => !q || s.id.toLowerCase().includes(q) || s.display_name.toLowerCase().includes(q));
  }, [list.data, extra, filter]);

  const save = useStudioMutation(() => api.setEnrollment(subjectId, [...selected]), "Assignments saved");
  const dirty = saved.size !== selected.size || [...selected].some((id) => !saved.has(id));

  if (isDefault) {
    return <p className="text-sm text-muted-foreground">Every student is enrolled in the built-in Data Structures course.</p>;
  }
  if (list.isLoading) return <Skeleton className="h-64 w-full rounded-xl" />;

  const toggle = (id: string, on: boolean) => {
    const next = new Set(selected);
    if (on) next.add(id);
    else next.delete(id);
    setSelected(next);
  };
  const addId = () => {
    const id = newId.trim();
    if (!VALID.test(id)) return;
    setExtra([id, ...extra]);
    toggle(id, true);
    setNewId("");
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Assign to students</CardTitle>
        <CardDescription>
          Assigned students get this subject in their subject switcher{published ? "." : " once you publish it."} Use
          pseudonymous IDs only.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="flex flex-wrap gap-2">
          <Input className="max-w-xs" placeholder="Filter students" value={filter} onChange={(e) => setFilter(e.target.value)} />
          <div className="flex gap-2">
            <Input className="w-48 font-mono text-xs" placeholder="Add student ID" value={newId}
              onChange={(e) => setNewId(e.target.value.trim())} onKeyDown={(e) => e.key === "Enter" && addId()} />
            <Button variant="outline" disabled={!VALID.test(newId)} onClick={addId}><UserPlusIcon /> Add</Button>
          </div>
        </div>
        <div className="flex items-center gap-3 text-sm">
          <Button variant="ghost" size="sm" onClick={() => setSelected(new Set(rows.map((r) => r.id)))}>Select all shown</Button>
          <Button variant="ghost" size="sm" onClick={() => setSelected(new Set())}>Clear</Button>
          <span className="text-muted-foreground">{selected.size} assigned</span>
        </div>
        <div className="max-h-96 divide-y overflow-y-auto rounded-lg border">
          {rows.length === 0 ? (
            <p className="p-4 text-sm text-muted-foreground">No students yet. Add a student ID above.</p>
          ) : (
            rows.map((s) => (
              <label key={s.id} className="flex cursor-pointer items-center gap-3 px-3 py-2 text-sm hover:bg-muted/40">
                <input type="checkbox" className="size-4 accent-[var(--primary)]" checked={selected.has(s.id)}
                  onChange={(e) => toggle(s.id, e.target.checked)} />
                <span className="flex-1">{s.display_name}</span>
                <span className="font-mono text-xs text-muted-foreground">{s.id}</span>
              </label>
            ))
          )}
        </div>
        <div className="flex justify-end">
          <Button disabled={!dirty || save.isPending}
            onClick={() => save.mutate(undefined, { onSuccess: () => { setExtra([]); setDraft(null); } })}>
            <SaveIcon /> {save.isPending ? "Saving..." : "Save assignments"}
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
