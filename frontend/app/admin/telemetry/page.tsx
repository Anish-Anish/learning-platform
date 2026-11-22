"use client";

import { DatabaseIcon, ExternalLinkIcon, RadioTowerIcon } from "lucide-react";

import { ErrorNote, fmt, KV, Loading, PageHeader, Panel, Stat } from "@/components/admin/kit";
import { ExportRows, openObserveUrl } from "@/components/admin/telemetry-summary";
import { Button } from "@/components/ui/button";
import { useTelemetry } from "@/lib/queries/admin";

const SETUP = `# 1. Start OpenObserve locally (needs Docker Desktop running)
docker compose -f deploy/openobserve/docker-compose.yml up -d

# 2. In backend/.env
OTEL_ENABLED=true
OTEL_EXPORTER_ENDPOINT=http://localhost:5080/api/default
OPENOBSERVE_USER=root@rootwise.local
OPENOBSERVE_PASSWORD=Change-Me-Rootwise-1!

# 3. Restart the backend, then open http://localhost:5080`;

export default function AdminTelemetry() {
  const telemetry = useTelemetry();
  const t = telemetry.data;
  if (!t) return telemetry.error ? <ErrorNote error={telemetry.error} /> : <Loading />;
  return (
    <div className="space-y-5">
      <PageHeader title="Telemetry"
        description="OpenTelemetry traces, metrics and logs exported over OTLP/HTTP, plus what the app stores itself." />
      <div className="grid gap-3 sm:grid-cols-3">
        <Stat icon={RadioTowerIcon} label="OpenTelemetry" value={t.otel_enabled ? "Exporting" : "Off"}
          tone={t.otel_enabled ? "good" : "default"} sub={t.otel_enabled ? `${t.service_name} · ${t.environment}` : "set OTEL_ENABLED=true"} />
        <Stat icon={DatabaseIcon} label="Stored logs" value={fmt.int(t.stored.app_logs)}
          sub={`kept ${t.retention.log_days} days, max ${fmt.int(t.retention.log_max_rows)} rows`} />
        <Stat icon={DatabaseIcon} label="Stored request metrics" value={fmt.int(t.stored.request_metrics)}
          sub={`kept ${t.retention.request_metrics_days} days · ${fmt.int(t.stored.llm_calls)} LLM calls`} />
      </div>
      {t.otel_enabled ? (
        <div className="grid gap-5 xl:grid-cols-2">
          <Panel title="Export health" description="Counted by the exporters themselves (spans and log records)">
            <ExportRows t={t} />
          </Panel>
          <Panel title="Configuration">
            <KV rows={[
              ["OTLP endpoint", t.endpoint ?? "–"],
              ["Auth configured", t.auth_configured ? "yes" : "no"],
              ["Trace sample ratio", fmt.pct(t.sample_ratio, 0)],
              ["OpenObserve org", t.openobserve_org],
            ]} />
            <div className="mt-4 flex flex-wrap gap-2">
              {(["traces", "logs", "metrics"] as const).map((v) => (
                <Button key={v} variant="secondary" size="sm" asChild>
                  <a href={openObserveUrl(t, v)} target="_blank" rel="noreferrer">Open {v} <ExternalLinkIcon /></a>
                </Button>
              ))}
            </div>
          </Panel>
        </div>
      ) : (
        <Panel title="Turn on OpenObserve export" description="Everything else on these pages already works from the app's own store.">
          <pre className="overflow-x-auto rounded-lg bg-muted p-4 text-xs">{SETUP}</pre>
        </Panel>
      )}
      <Panel title="What gets exported">
        <KV rows={[
          ["Request spans", "one per API call (route, status, student, subject)"],
          ["LLM spans", "gen_ai.* tokens, model, cost, fallback, guardrail flags (never prompt text)"],
          ["Studio spans", "job → figures → extract → graph → per-concept authoring"],
          ["Metrics", "rootwise.llm.calls/tokens/cost/duration, guardrail flags, studio jobs, HTTP server"],
          ["Logs", "every structured log event, linked to its trace"],
          ["Trace ids", "the app's trace id is tr_<OTel trace id>, so rows, logs and spans line up"],
        ]} />
      </Panel>
    </div>
  );
}
