"use client";

import { GraduationCapIcon } from "lucide-react";
import Link from "next/link";

import { StateBadge } from "@/components/state-badge";
import { Card, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useStudentMap } from "@/lib/queries/student";
import { useSession } from "@/lib/store";

export default function TeachIndex() {
  const studentId = useSession((s) => s.studentId);
  const map = useStudentMap(studentId);
  const nodes = (map.data?.nodes ?? []).filter((n) => n.state !== "locked");
  return (
    <div className="space-y-4">
      <div>
        <h1 className="flex items-center gap-2 text-2xl font-semibold tracking-tight">
          <GraduationCapIcon className="size-6 text-primary" /> Teach the bot
        </h1>
        <p className="text-sm text-muted-foreground">
          Feynman mode: explain a concept to Byte, a curious (and slightly confused) classmate. Score 80+ for bonus XP.
        </p>
      </div>
      {map.isLoading ? (
        <Skeleton className="h-60 w-full" />
      ) : (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {nodes.map((n) => (
            <Link key={n.id} href={`/teach/${n.id}`}>
              <Card className="h-full transition-colors hover:border-primary/60 hover:bg-primary/5">
                <CardHeader>
                  <CardTitle className="text-base">{n.name}</CardTitle>
                  <CardDescription>
                    <StateBadge state={n.state} />
                  </CardDescription>
                </CardHeader>
              </Card>
            </Link>
          ))}
          {nodes.length === 0 && <p className="text-sm text-muted-foreground">Unlock a concept first by learning.</p>}
        </div>
      )}
    </div>
  );
}
