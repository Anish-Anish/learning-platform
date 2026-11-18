"use client";

import Link from "next/link";
import { useMemo } from "react";

import { ReportView } from "@/components/report-view";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useConcepts, useReport } from "@/lib/queries/student";
import { useSession } from "@/lib/store";

export default function ReportPage() {
  const studentId = useSession((s) => s.studentId);
  const report = useReport(studentId);
  const concepts = useConcepts();
  const names = useMemo(() => Object.fromEntries((concepts.data ?? []).map((c) => [c.id, c.name])), [concepts.data]);
  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Root Report</h1>
        <p className="text-sm text-muted-foreground">Your top root gaps, how well your confidence matches reality, and what to do next.</p>
      </div>
      {report.isLoading ? (
        <div className="grid gap-4">
          <Skeleton className="h-24 w-full" />
          <Skeleton className="h-72 w-full" />
        </div>
      ) : report.error ? (
        <Card>
          <CardHeader>
            <CardTitle>No report yet</CardTitle>
            <CardDescription>Answer a few questions first.</CardDescription>
          </CardHeader>
          <CardContent>
            <Button asChild>
              <Link href="/learn">Start learning</Link>
            </Button>
          </CardContent>
        </Card>
      ) : report.data ? (
        <ReportView report={report.data} names={names} />
      ) : null}
    </div>
  );
}
