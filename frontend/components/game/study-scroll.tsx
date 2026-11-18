"use client";

import { BookOpenIcon, CheckCircle2Icon, LightbulbIcon, ShieldAlertIcon } from "lucide-react";

import { RichText } from "@/components/rich-text";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { Skeleton } from "@/components/ui/skeleton";
import { useConceptDetail } from "@/lib/queries/game";

/** Self-study: the teacher's notes, key ideas and common traps, before (or after) playing a level. */
export function StudyScroll({ conceptId, open, onOpenChange }: { conceptId: string | null; open: boolean; onOpenChange: (o: boolean) => void }) {
  const detail = useConceptDetail(open ? conceptId : null);
  const d = detail.data;
  const paragraphs = (d?.notes_md ?? "")
    .split(/\n\s*\n/)
    .map((p) => p.trim())
    .filter((p) => p && !p.startsWith("#"));
  const example = paragraphs.find((p) => p.startsWith("**Example"));
  const body = paragraphs.filter((p) => p !== example);
  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent className="w-full sm:max-w-xl" data-accent="violet">
        <SheetHeader>
          <div className="flex items-center gap-2 text-xs font-semibold tracking-wide text-primary uppercase">
            <BookOpenIcon className="size-4" /> Study scroll
          </div>
          <SheetTitle className="text-xl">{d?.name ?? <Skeleton className="h-6 w-48" />}</SheetTitle>
          <SheetDescription>{d?.description}</SheetDescription>
        </SheetHeader>
        <ScrollArea className="h-[calc(100vh-9rem)] px-4">
          {!d ? (
            <div className="space-y-2">
              <Skeleton className="h-20 w-full" />
              <Skeleton className="h-40 w-full" />
            </div>
          ) : (
            <div className="space-y-5 pb-8">
              <div className="rounded-xl border border-primary/30 bg-primary/5 p-4">
                <p className="mb-2 text-xs font-semibold text-primary">Key ideas to remember</p>
                <ul className="space-y-1.5 text-sm">
                  {d.key_points.map((k) => (
                    <li key={k} className="flex gap-2">
                      <CheckCircle2Icon className="mt-0.5 size-4 shrink-0 text-primary" /> {k}
                    </li>
                  ))}
                </ul>
              </div>
              <RichText text={body.join("\n\n")} />
              {example && (
                <div className="rounded-xl border bg-muted/40 p-4">
                  <p className="mb-1 flex items-center gap-1.5 text-xs font-semibold text-muted-foreground">
                    <LightbulbIcon className="size-3.5" /> Worked example
                  </p>
                  <RichText text={example.replace(/^\*\*Example\.?\*\*\s*/, "")} className="text-sm" />
                </div>
              )}
              {d.traps.length > 0 && (
                <div className="space-y-2">
                  <p className="flex items-center gap-1.5 text-xs font-semibold text-rose-600 dark:text-rose-400">
                    <ShieldAlertIcon className="size-3.5" /> Traps that catch players
                  </p>
                  {d.traps.map((t) => (
                    <div key={t.description} className="grid gap-2 rounded-xl border p-3 text-sm sm:grid-cols-2">
                      <p>
                        <span className="text-xs font-medium text-rose-600 dark:text-rose-400">❌ Myth: </span>
                        {t.description}
                      </p>
                      <p>
                        <span className="text-xs font-medium text-emerald-600 dark:text-emerald-400">✅ Truth: </span>
                        {t.correct_belief}
                      </p>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </ScrollArea>
      </SheetContent>
    </Sheet>
  );
}
