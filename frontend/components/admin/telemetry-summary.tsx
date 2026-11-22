"use client";

import { CheckCircle2Icon, CircleAlertIcon, CircleDashedIcon, ExternalLinkIcon } from "lucide-react";
import Link from "next/link";

import { fmt, Panel } from "@/components/admin/kit";
import { Button } from "@/components/ui/button";
import { useTelemetry } from "@/lib/queries/admin";
import type { TelemetryStatus } from "@/lib/types";

export function openObserveUrl(t: TelemetryStatus, view: "traces" | "logs" | "metrics") {
  return `${t.openobserve_ui_url.replace(/\/$/, "")}/web/${view}?org_identifier=${encodeURIComponent(t.openobserve_org)}`;
}

export function ExportRows({ t }: { t: TelemetryStatus }) {
  const signals = ["traces", "logs"] as const;
  return (
    <ul className="space-y-1.5 text-sm">
      {signals.map((s) => {
        const e = t.exports[s];
        const Icon = !e ? CircleDashedIcon : e.failed > 0 && !e.last_success_at ? CircleAlertIcon : CheckCircle2Icon;
        const tone = !e ? "text-muted-foreground" : e.failed > 0 && !e.last_success_at ? "text-destructive" : "text-emerald-600 dark:text-emerald-400";
        return (
          <li key={s} className="flex items-center gap-2">
            <Icon className={`size-4 ${tone}`} />
            <span className="w-14 capitalize">{s}</span>
            <span className="text-xs text-muted-foreground">
              {!e ? "nothing exported yet" : `${fmt.int(e.exported)} exported · ${fmt.int(e.failed)} failed · last ok ${fmt.time(e.last_success_at)}`}
            </span>
          </li>
        );
      })}
      {signals.map((s) => t.exports[s]?.last_error && (
        <li key={`${s}-err`} className="text-xs text-destructive">{s}: {t.exports[s]?.last_error}</li>
      ))}
    </ul>
  );
}

export function TelemetrySummary() {
  const t = useTelemetry().data;
  return (
    <Panel title="OpenTelemetry" description={t?.otel_enabled ? `Exporting to ${t.endpoint}` : "Export to OpenObserve is off"}
      action={<Button variant="outline" size="sm" asChild><Link href="/admin/telemetry">Details</Link></Button>}>
      {!t ? null : t.otel_enabled ? (
        <div className="space-y-3">
          <ExportRows t={t} />
          <div className="flex flex-wrap gap-2">
            {(["traces", "logs", "metrics"] as const).map((v) => (
              <Button key={v} variant="secondary" size="sm" asChild>
                <a href={openObserveUrl(t, v)} target="_blank" rel="noreferrer">
                  OpenObserve {v} <ExternalLinkIcon />
                </a>
              </Button>
            ))}
          </div>
        </div>
      ) : (
        <p className="text-sm text-muted-foreground">
          Metrics, traces and logs on this page come from the app&apos;s own store. Turn on OpenTelemetry to also ship them to
          OpenObserve: see <Link href="/admin/telemetry" className="text-primary underline-offset-4 hover:underline">Telemetry</Link>.
        </p>
      )}
    </Panel>
  );
}
