"use client";

import { BookOpenIcon } from "lucide-react";
import { useEffect, useMemo } from "react";

import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { useStudentSubjects, useSubjects, useSwitchSubject } from "@/lib/queries/studio";
import { DEFAULT_SUBJECT_ID, useSession } from "@/lib/store";

/** Students see subjects they're enrolled in; teachers see every published subject (scopes the dashboard). */
export function SubjectSwitcher({ variant }: { variant: "student" | "teacher" }) {
  const studentId = useSession((s) => s.studentId);
  const subjectId = useSession((s) => s.subjectId);
  const switchSubject = useSwitchSubject();
  const enrolled = useStudentSubjects(studentId, variant === "student");
  const all = useSubjects();
  const options = useMemo(
    () =>
      variant === "student"
        ? (enrolled.data?.subjects ?? []).map((s) => ({ id: s.id, name: s.name }))
        : (all.data?.subjects ?? []).filter((s) => s.status === "published").map((s) => ({ id: s.id, name: s.name })),
    [variant, enrolled.data, all.data],
  );
  const loaded = variant === "student" ? enrolled.isSuccess : all.isSuccess;

  // The active subject was unpublished or un-assigned: fall back to the built-in course.
  useEffect(() => {
    if (loaded && !options.some((o) => o.id === subjectId)) switchSubject(DEFAULT_SUBJECT_ID);
  }, [loaded, options, subjectId, switchSubject]);

  if (!loaded || options.length === 0) return null;
  return (
    <Select value={subjectId} onValueChange={switchSubject}>
      <SelectTrigger size="sm" className="max-w-44 shrink-0 gap-1.5 text-xs" aria-label="Subject">
        <BookOpenIcon className="size-3.5 text-muted-foreground" />
        <SelectValue />
      </SelectTrigger>
      <SelectContent align="end">
        {options.map((o) => (
          <SelectItem key={o.id} value={o.id}>
            {o.name}
          </SelectItem>
        ))}
        {options.length === 1 && (
          <p className="max-w-56 px-2 py-1.5 text-xs text-muted-foreground">
            {variant === "student"
              ? "More subjects appear here when your teacher publishes and assigns them."
              : "Publish a subject in the Studio to see its class data here."}
          </p>
        )}
      </SelectContent>
    </Select>
  );
}
