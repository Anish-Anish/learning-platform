"use client";

import { UserRoundIcon } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useSession } from "@/lib/store";

export function StudentSwitcher() {
  const studentId = useSession((s) => s.studentId);
  const setStudent = useSession((s) => s.setStudent);
  const [value, setValue] = useState(studentId);
  const [open, setOpen] = useState(false);
  const valid = /^[A-Za-z0-9_-]{1,64}$/.test(value);
  return (
    <Dialog open={open} onOpenChange={(o) => { setOpen(o); setValue(studentId); }}>
      <DialogTrigger asChild>
        <Button variant="ghost" size="sm" className="gap-1.5 text-muted-foreground">
          <UserRoundIcon className="size-4" />
          <span className="max-w-28 truncate font-mono text-xs">{studentId}</span>
        </Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Switch learner</DialogTitle>
          <DialogDescription>
            Rootwise uses pseudonymous IDs only. Names never reach the AI. Use a new ID to start fresh.
          </DialogDescription>
        </DialogHeader>
        <div className="grid gap-2">
          <Label htmlFor="sid">Student ID</Label>
          <Input id="sid" value={value} onChange={(e) => setValue(e.target.value.trim())} placeholder="demo_student" />
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => setValue(`learner_${Math.random().toString(36).slice(2, 7)}`)}>
            Random ID
          </Button>
          <Button disabled={!valid} onClick={() => { setStudent(value); setOpen(false); }}>
            Use this ID
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
