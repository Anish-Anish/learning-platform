"use client";

import { FileTextIcon } from "lucide-react";

import { formatBytes } from "@/components/studio/dropzone";
import { Badge } from "@/components/ui/badge";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import type { SourceDocument } from "@/lib/types";

const num = (v: unknown) => (typeof v === "number" ? v : 0);

export function SourcesTable({ documents, stats }: { documents: SourceDocument[]; stats: Record<string, unknown> }) {
  return (
    <div className="space-y-4">
      <div className="overflow-x-auto rounded-xl border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>File</TableHead>
              <TableHead className="text-right">Size</TableHead>
              <TableHead className="text-right">Pages</TableHead>
              <TableHead className="text-right">Tables</TableHead>
              <TableHead className="text-right">Figures</TableHead>
              <TableHead className="text-right">Scanned</TableHead>
              <TableHead>Status</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {documents.map((d) => {
              const s = d.parse_stats ?? {};
              return (
                <TableRow key={d.id}>
                  <TableCell className="max-w-72">
                    <span className="flex items-center gap-2"><FileTextIcon className="size-4 shrink-0 text-muted-foreground" /><span className="truncate">{d.filename}</span></span>
                    {d.error && <p className="mt-1 text-xs text-destructive">{d.error}</p>}
                    {num(s.truncated_pages) > 0 && <p className="mt-1 text-xs text-amber-600">Only the first {num(s.pages)} pages were read.</p>}
                  </TableCell>
                  <TableCell className="text-right tabular-nums">{formatBytes(d.size_bytes)}</TableCell>
                  <TableCell className="text-right tabular-nums">{d.page_count || "–"}</TableCell>
                  <TableCell className="text-right tabular-nums">{num(s.tables)}</TableCell>
                  <TableCell className="text-right tabular-nums">{num(s.figures)}</TableCell>
                  <TableCell className="text-right tabular-nums">{num(s.scanned_pages)}</TableCell>
                  <TableCell>
                    <Badge variant={d.status === "failed" ? "destructive" : "secondary"} className="capitalize">{d.status}</Badge>
                  </TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      </div>
      {Object.keys(stats).length > 0 && (
        <div className="grid gap-2 text-sm sm:grid-cols-3 lg:grid-cols-6">
          {[
            ["Sections read", stats.chunks],
            ["Concept candidates", stats.candidates],
            ["Figures described", stats.figures_described],
            ["Decorative skipped", stats.figures_decorative],
            ["Pages OCR'd", stats.pages_ocr],
            ["Misconceptions", stats.misconceptions],
          ].map(([label, v]) => (
            <div key={String(label)} className="rounded-lg border p-2.5">
              <p className="text-xs text-muted-foreground">{String(label)}</p>
              <p className="font-semibold tabular-nums">{num(v)}</p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
