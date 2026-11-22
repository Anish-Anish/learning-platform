"use client";

import { ArrowLeftIcon } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useMemo } from "react";

import { SkillTree, StateLegend } from "@/components/graph/skill-tree";
import { ReportView } from "@/components/report-view";
import { LevelDifficulty, RunFeed } from "@/components/teacher/game-results";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { useClassGame } from "@/lib/queries/game";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useConcepts, useReport, useStudent, useStudentMap } from "@/lib/queries/student";

export default function TeacherStudentPage() {
  const { id } = useParams<{ id: string }>();
  const student = useStudent(id);
  const map = useStudentMap(id);
  const report = useReport(id);
  const concepts = useConcepts();
  const game = useClassGame(id);
  const me = game.data?.students.find((s) => s.student_id === id);
  const names = useMemo(() => Object.fromEntries((concepts.data ?? []).map((c) => [c.id, c.name])), [concepts.data]);
  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3">
        <Button variant="ghost" size="icon" asChild>
          <Link href="/teacher" aria-label="Back to dashboard">
            <ArrowLeftIcon />
          </Link>
        </Button>
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">{student.data?.display_name ?? id}</h1>
          <p className="font-mono text-xs text-muted-foreground">
            {id}
            {student.data?.is_simulated && " · simulated student"}
          </p>
        </div>
      </div>
      <Tabs defaultValue="report">
        <TabsList>
          <TabsTrigger value="report">Root report</TabsTrigger>
          <TabsTrigger value="map">Knowledge map</TabsTrigger>
          <TabsTrigger value="game">🎮 Game results</TabsTrigger>
        </TabsList>
        <TabsContent value="report" className="pt-3">
          {report.data ? <ReportView report={report.data} names={names} teacher /> : <Skeleton className="h-96 w-full" />}
        </TabsContent>
        <TabsContent value="game" className="pt-3">
          {game.data ? (
            <div className="grid gap-4 lg:grid-cols-2">
              <Card>
                <CardHeader>
                  <CardTitle>Runs</CardTitle>
                  <CardDescription>
                    {me ? `${me.stars} stars · ${me.levels_completed} levels cleared · ${me.wins} won / ${me.fails} lost · best combo x${me.best_combo}` : "No Adventure runs yet."}
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <RunFeed runs={game.data.recent_runs} showStudent={false} />
                </CardContent>
              </Card>
              <Card>
                <CardHeader>
                  <CardTitle>Levels played</CardTitle>
                  <CardDescription>Clear rate per level for this student, with their most common trap.</CardDescription>
                </CardHeader>
                <CardContent>
                  <LevelDifficulty levels={game.data.levels} />
                </CardContent>
              </Card>
            </div>
          ) : (
            <Skeleton className="h-64 w-full" />
          )}
        </TabsContent>
        <TabsContent value="map" className="space-y-3 pt-3">
          <StateLegend />
          {map.data ? <SkillTree map={map.data} /> : <Skeleton className="h-[640px] w-full" />}
        </TabsContent>
      </Tabs>
    </div>
  );
}
