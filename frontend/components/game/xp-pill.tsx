"use client";

import { SparklesIcon } from "lucide-react";
import { animate, motion, useMotionValue, useTransform } from "motion/react";
import { useEffect } from "react";

import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { XP_PER_LEVEL, useSession } from "@/lib/store";

export function XpPill() {
  const xp = useSession((s) => s.xp);
  const level = useSession((s) => s.level);
  const mv = useMotionValue(xp);
  const shown = useTransform(mv, (v) => Math.round(v).toString());
  useEffect(() => {
    const c = animate(mv, xp, { duration: 0.8, ease: "easeOut" });
    return () => c.stop();
  }, [xp, mv]);
  const into = ((xp % XP_PER_LEVEL) + XP_PER_LEVEL) % XP_PER_LEVEL;
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <div className="flex items-center gap-2 rounded-full border bg-card px-3 py-1 text-sm shadow-xs">
          <span className="grid size-5 place-items-center rounded-full bg-primary text-[10px] font-bold text-primary-foreground">
            {level}
          </span>
          <div className="hidden h-1.5 w-20 overflow-hidden rounded-full bg-muted sm:block">
            <motion.div
              className="h-full rounded-full bg-primary"
              animate={{ width: `${(into / XP_PER_LEVEL) * 100}%` }}
              transition={{ duration: 0.8 }}
            />
          </div>
          <SparklesIcon className="size-3.5 text-primary" />
          <motion.span className="tabular-nums font-medium">{shown}</motion.span>
          <span className="text-muted-foreground">XP</span>
        </div>
      </TooltipTrigger>
      <TooltipContent>XP only comes from mastery events: mastering, clearing misconceptions, beating bosses.</TooltipContent>
    </Tooltip>
  );
}
