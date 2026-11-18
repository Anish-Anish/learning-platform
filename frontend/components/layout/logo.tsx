import Link from "next/link";

export function Logo({ href = "/" }: { href?: string }) {
  return (
    <Link href={href} className="flex items-center gap-2 font-semibold tracking-tight">
      <span className="grid size-7 place-items-center rounded-lg bg-primary text-primary-foreground">
        <svg viewBox="0 0 24 24" className="size-4" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round">
          <path d="M12 3v8" />
          <path d="M12 11c-3 0-5 2-6 5" />
          <path d="M12 11c3 0 5 2 6 5" />
          <path d="M12 11v9" />
          <circle cx="6" cy="18" r="1.6" fill="currentColor" />
          <circle cx="18" cy="18" r="1.6" fill="currentColor" />
          <circle cx="12" cy="21" r="1.6" fill="currentColor" />
        </svg>
      </span>
      <span>Rootwise</span>
    </Link>
  );
}
