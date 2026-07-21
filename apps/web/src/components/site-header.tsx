"use client";

import { Activity, ArrowRight } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";

import { Button } from "@/components/ui/button";

const links = [
  ["Product", "/#product"],
  ["CLI workflow", "/#developer-workflow"],
  ["Reference run", "/run/opsroute-qwen-olmo/"],
  ["Assurance Lab", "/sandbox/"],
];

export function SiteHeader() {
  const pathname = usePathname();
  const activeHref = [...links]
    .sort((left, right) => right[1].length - left[1].length)
    .find(([, href]) => {
      if (href.includes("#") || href.startsWith("http")) return false;
      const normalizedHref = href.replace(/\/$/, "");
      return pathname === normalizedHref || pathname.startsWith(`${normalizedHref}/`);
    })?.[1];

  return (
    <header className="sticky top-0 z-40 border-b border-white/8 bg-slate-950/80 backdrop-blur-xl">
      <div className="mx-auto flex h-16 max-w-7xl items-center gap-6 px-4 sm:px-6 lg:px-8">
        <Link
          href="/"
          aria-label="InheritBench home"
          className="flex shrink-0 items-center gap-2 font-semibold text-white"
        >
          <span className="grid h-8 w-8 place-items-center rounded-lg border border-cyan-300/30 bg-cyan-300/10 text-cyan-200">
            <Activity className="h-4 w-4" />
          </span>
          <span className="hidden min-[480px]:inline">InheritBench</span>
        </Link>
        <nav aria-label="Primary" className="hidden flex-1 items-center gap-1 lg:flex">
          {links.map(([label, href]) => {
            const className = `rounded-full px-3 py-2 text-[0.9375rem] transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-300 ${
              activeHref === href
                ? "bg-cyan-300/10 text-cyan-100 shadow-[inset_0_0_0_1px_rgba(103,232,249,.16)]"
                : "text-slate-400 hover:bg-white/5 hover:text-white"
            }`;
            return href.startsWith("http") ? (
              <a key={href} href={href} className={className}>{label}</a>
            ) : (
              <Link key={href} href={href} aria-current={activeHref === href ? "page" : undefined} className={className}>
                {label}
              </Link>
            );
          })}
        </nav>
        <a
          href="https://github.com/faizanprofitpilot/InheritBench"
          target="_blank"
          rel="noreferrer"
          className="ml-auto inline-flex items-center gap-2 rounded-full px-3 py-2 text-sm font-medium text-slate-300 transition hover:bg-white/5 hover:text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-300"
        >
          GitHub <GitHubMark className="h-4 w-4" />
        </a>
        <Button asChild size="sm">
          <Link href="/#developer-workflow">
            View workflow <ArrowRight className="h-4 w-4" />
          </Link>
        </Button>
      </div>
      <nav aria-label="Mobile primary" className="flex gap-1 overflow-x-auto px-4 pb-2 lg:hidden">
        {links.map(([label, href]) => {
          const className = `whitespace-nowrap rounded-full px-3 py-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-300 ${
            activeHref === href
              ? "bg-cyan-300/10 text-cyan-100 shadow-[inset_0_0_0_1px_rgba(103,232,249,.16)]"
              : "text-slate-400 hover:bg-white/5 hover:text-white"
          }`;
          return href.startsWith("http") ? (
            <a key={href} href={href} className={className}>{label}</a>
          ) : (
            <Link key={href} href={href} aria-current={activeHref === href ? "page" : undefined} className={className}>
              {label}
            </Link>
          );
        })}
      </nav>
    </header>
  );
}

function GitHubMark({ className }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="currentColor"
      className={className}
      aria-hidden="true"
    >
      <path d="M12 .7a11.5 11.5 0 0 0-3.64 22.41c.58.11.79-.25.79-.56v-2.24c-3.22.7-3.9-1.37-3.9-1.37-.53-1.34-1.29-1.7-1.29-1.7-1.05-.72.08-.7.08-.7 1.16.08 1.77 1.19 1.77 1.19 1.04 1.77 2.71 1.26 3.37.96.1-.75.4-1.26.73-1.55-2.57-.29-5.27-1.28-5.27-5.68 0-1.26.45-2.28 1.18-3.09-.12-.29-.51-1.46.11-3.05 0 0 .96-.31 3.16 1.18A10.9 10.9 0 0 1 12 6.11c.98 0 1.95.13 2.87.39 2.19-1.49 3.15-1.18 3.15-1.18.63 1.59.24 2.76.12 3.05.74.81 1.18 1.83 1.18 3.09 0 4.42-2.71 5.38-5.29 5.67.42.36.79 1.07.79 2.16v3.26c0 .31.21.68.8.56A11.5 11.5 0 0 0 12 .7Z" />
    </svg>
  );
}
