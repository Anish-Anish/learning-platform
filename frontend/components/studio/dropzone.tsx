"use client";

import { FileTextIcon, UploadCloudIcon, XIcon } from "lucide-react";
import { useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

const ACCEPT = [".pdf", ".md", ".markdown", ".txt"];
export const MAX_FILES = 10;
export const MAX_MB = 200;

export function formatBytes(n: number) {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(0)} KB`;
  return `${(n / 1024 / 1024).toFixed(1)} MB`;
}

function accepted(f: File) {
  return ACCEPT.some((ext) => f.name.toLowerCase().endsWith(ext));
}

export function Dropzone({ files, onChange, max = MAX_FILES }: { files: File[]; onChange: (f: File[]) => void; max?: number }) {
  const input = useRef<HTMLInputElement>(null);
  const [over, setOver] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const add = (list: FileList | null) => {
    if (!list) return;
    const incoming = Array.from(list);
    const bad = incoming.filter((f) => !accepted(f));
    const big = incoming.filter((f) => f.size > MAX_MB * 1024 * 1024);
    const ok = incoming.filter((f) => accepted(f) && f.size <= MAX_MB * 1024 * 1024);
    const merged = [...files, ...ok.filter((f) => !files.some((x) => x.name === f.name && x.size === f.size))].slice(0, max);
    setError(
      bad.length
        ? `Skipped ${bad.map((f) => f.name).join(", ")}: only PDF, Markdown or text files.`
        : big.length
          ? `Skipped ${big.map((f) => f.name).join(", ")}: larger than ${MAX_MB} MB.`
          : files.length + ok.length > max
            ? `Up to ${max} files per upload.`
            : null,
    );
    onChange(merged);
  };

  return (
    <div className="space-y-2">
      <button
        type="button"
        onClick={() => input.current?.click()}
        onDragOver={(e) => {
          e.preventDefault();
          setOver(true);
        }}
        onDragLeave={() => setOver(false)}
        onDrop={(e) => {
          e.preventDefault();
          setOver(false);
          add(e.dataTransfer.files);
        }}
        className={cn(
          "flex w-full flex-col items-center gap-2 rounded-xl border-2 border-dashed px-4 py-8 text-center transition-colors",
          over ? "border-primary bg-primary/5" : "border-muted-foreground/25 hover:border-primary/60 hover:bg-muted/40",
        )}
      >
        <UploadCloudIcon className="size-8 text-primary" />
        <span className="text-sm font-medium">Drop PDFs, notes or chapters here, or click to browse</span>
        <span className="text-xs text-muted-foreground">
          PDF (text, tables, diagrams, scans), Markdown or text · up to {max} files, {MAX_MB} MB each
        </span>
      </button>
      <input
        ref={input}
        type="file"
        multiple
        accept={ACCEPT.join(",")}
        className="hidden"
        onChange={(e) => {
          add(e.target.files);
          e.target.value = "";
        }}
      />
      {error && <p className="text-xs text-destructive">{error}</p>}
      {files.length > 0 && (
        <ul className="divide-y rounded-lg border">
          {files.map((f, i) => (
            <li key={`${f.name}-${i}`} className="flex items-center gap-2 px-3 py-2 text-sm">
              <FileTextIcon className="size-4 shrink-0 text-muted-foreground" />
              <span className="flex-1 truncate">{f.name}</span>
              <span className="text-xs tabular-nums text-muted-foreground">{formatBytes(f.size)}</span>
              <Button
                type="button"
                variant="ghost"
                size="icon-xs"
                aria-label={`Remove ${f.name}`}
                onClick={() => onChange(files.filter((_, j) => j !== i))}
              >
                <XIcon />
              </Button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
