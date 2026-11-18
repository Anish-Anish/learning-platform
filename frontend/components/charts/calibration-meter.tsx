import type { RootReport } from "@/lib/types";
import { cn } from "@/lib/utils";

/** Semi-circular gauge for the calibration score + the confidence matrix counts. */
export function CalibrationMeter({ cal }: { cal: RootReport["calibration"] }) {
  const score = cal.score ?? 0;
  const angle = -90 + score * 180;
  const tone = score >= 0.8 ? "text-emerald-500" : score >= 0.5 ? "text-amber-500" : "text-rose-500";
  return (
    <div className="space-y-3">
      <div className="relative mx-auto h-28 w-52">
        <svg viewBox="0 0 200 110" className="h-full w-full">
          <path d="M15 100 A85 85 0 0 1 185 100" fill="none" stroke="var(--muted)" strokeWidth="14" strokeLinecap="round" />
          <path
            d="M15 100 A85 85 0 0 1 185 100"
            fill="none"
            stroke="currentColor"
            className={tone}
            strokeWidth="14"
            strokeLinecap="round"
            pathLength={100}
            strokeDasharray={`${score * 100} 100`}
          />
          <line
            x1="100" y1="100" x2="100" y2="30"
            stroke="currentColor" strokeWidth="3" strokeLinecap="round"
            className="text-foreground transition-transform duration-700"
            style={{ transform: `rotate(${angle}deg)`, transformOrigin: "100px 100px" }}
          />
          <circle cx="100" cy="100" r="6" className="fill-foreground" />
        </svg>
        <div className="absolute inset-x-0 bottom-0 text-center">
          <span className={cn("text-2xl font-semibold tabular-nums", tone)}>{cal.score == null ? "–" : `${Math.round(score * 100)}%`}</span>
        </div>
      </div>
      <p className="text-center text-xs text-muted-foreground">How often your confidence matched the result ({cal.n} answers)</p>
      <div className="grid grid-cols-2 gap-1.5 text-xs">
        <div className="rounded-md bg-emerald-500/10 p-2">Sure &amp; right <b className="float-right tabular-nums">{cal.sure_correct}</b></div>
        <div className="rounded-md bg-rose-500/10 p-2">Sure &amp; wrong <b className="float-right tabular-nums">{cal.sure_wrong}</b></div>
        <div className="rounded-md bg-amber-500/10 p-2">Guess &amp; right <b className="float-right tabular-nums">{cal.guess_correct}</b></div>
        <div className="rounded-md bg-orange-500/10 p-2">Guess &amp; wrong <b className="float-right tabular-nums">{cal.guess_wrong}</b></div>
      </div>
    </div>
  );
}
