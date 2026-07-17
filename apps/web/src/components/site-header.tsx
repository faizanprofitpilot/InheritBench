"use client";

import { Activity, Code2 } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";

import { Button } from "@/components/ui/button";

const links = [
  ["Run Replay", "/run/opsroute-qwen-olmo"],
  ["Succession Case", "/lab/opsroute"],
  ["Recovery Paths", "/lab/opsroute/methods"],
  ["Failure Explorer", "/lab/opsroute/failures"],
  ["Recommendation", "/lab/opsroute/memo"],
  ["Evidence", "/lab/opsroute/evidence"],
];

export function SiteHeader() {
  const pathname = usePathname();
  const activeHref = [...links]
    .sort((left, right) => right[1].length - left[1].length)
    .find(([, href]) => pathname === href || pathname.startsWith(`${href}/`))?.[1];

  return (
    <header className="sticky top-0 z-40 border-b border-white/8 bg-slate-950/80 backdrop-blur-xl">
      <div className="mx-auto flex h-16 max-w-7xl items-center gap-6 px-4 sm:px-6 lg:px-8">
        <Link href="/" className="flex items-center gap-2 font-semibold text-white">
          <span className="grid h-8 w-8 place-items-center rounded-lg border border-cyan-300/30 bg-cyan-300/10 text-cyan-200">
            <Activity className="h-4 w-4" />
          </span>
          <span>InheritBench</span>
        </Link>
        <nav aria-label="Primary" className="hidden flex-1 items-center gap-1 lg:flex">
          {links.map(([label, href]) => (
            <Link
              key={href}
              href={href}
              aria-current={activeHref === href ? "page" : undefined}
              className={`rounded-full px-3 py-2 text-[0.9375rem] transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-300 ${
                activeHref === href
                  ? "bg-cyan-300/10 text-cyan-100 shadow-[inset_0_0_0_1px_rgba(103,232,249,.16)]"
                  : "text-slate-400 hover:bg-white/5 hover:text-white"
              }`}
            >
              {label}
            </Link>
          ))}
        </nav>
        <Button asChild variant="secondary" size="sm" className="ml-auto">
          <a href="https://github.com/faizanprofitpilot/InheritBench">
            <Code2 className="h-4 w-4" />
            Repository
          </a>
        </Button>
      </div>
      <nav aria-label="Lab sections" className="flex gap-1 overflow-x-auto px-4 pb-2 lg:hidden">
        {links.map(([label, href]) => (
          <Link
            key={href}
            href={href}
            aria-current={activeHref === href ? "page" : undefined}
            className={`whitespace-nowrap rounded-full px-3 py-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-300 ${
              activeHref === href
                ? "bg-cyan-300/10 text-cyan-100 shadow-[inset_0_0_0_1px_rgba(103,232,249,.16)]"
                : "text-slate-400 hover:bg-white/5 hover:text-white"
            }`}
          >
            {label}
          </Link>
        ))}
      </nav>
    </header>
  );
}
