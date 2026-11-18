import { Fragment } from "react";

import { cn } from "@/lib/utils";

// Tiny, safe Markdown subset renderer: paragraphs, **bold**, `inline code` and ``` code blocks.
// Builds React nodes (no dangerouslySetInnerHTML), so model/student text can never inject HTML.
function inline(text: string, keyPrefix: string) {
  const parts = text.split(/(\*\*[^*]+\*\*|`[^`]+`)/g);
  return parts.map((p, i) => {
    const k = `${keyPrefix}-${i}`;
    if (p.startsWith("**") && p.endsWith("**")) return <strong key={k}>{p.slice(2, -2)}</strong>;
    if (p.startsWith("`") && p.endsWith("`") && p.length > 1) return <code key={k}>{p.slice(1, -1)}</code>;
    return <Fragment key={k}>{p}</Fragment>;
  });
}

export function RichText({ text, className, streaming }: { text: string; className?: string; streaming?: boolean }) {
  const blocks = text.split(/```(?:\w+)?\n?/);
  return (
    <div className={cn("prose-lesson rw-code text-[0.95rem]", className, streaming && "rw-caret")}>
      {blocks.map((b, i) =>
        i % 2 === 1 ? (
          <pre key={i} className="my-3 overflow-x-auto rounded-lg border bg-muted/60 p-3 font-mono text-[0.82rem] leading-relaxed">
            {b.replace(/\n$/, "")}
          </pre>
        ) : (
          b
            .split(/\n\s*\n/)
            .filter((p) => p.trim())
            .map((p, j) => <p key={`${i}-${j}`}>{inline(p.trim(), `${i}-${j}`)}</p>)
        ),
      )}
    </div>
  );
}
