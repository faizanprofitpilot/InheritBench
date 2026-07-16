"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const sections = [
  ["Overview", "/lab/opsroute"],
  ["Methods", "/lab/opsroute/methods"],
  ["Failures", "/lab/opsroute/failures"],
  ["Memo", "/lab/opsroute/memo"],
  ["Evidence", "/lab/opsroute/evidence"],
] as const;

export function LabNavigation() {
  const pathname = usePathname();
  const activeHref = [...sections]
    .sort((left, right) => right[1].length - left[1].length)
    .find(([, href]) => pathname === href || pathname.startsWith(`${href}/`))?.[1];

  return (
    <nav aria-label="OpsRoute sections" className="mb-12 flex gap-2 overflow-x-auto border-b border-white/8 pb-4">
      {sections.map(([label, href]) => {
        const active = activeHref === href;
        return (
          <Link
            key={href}
            href={href}
            aria-current={active ? "page" : undefined}
            className={`whitespace-nowrap rounded-full border px-4 py-2.5 text-[0.9375rem] font-medium transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-300 ${
              active
                ? "border-cyan-300/30 bg-cyan-300/10 text-cyan-100"
                : "border-white/10 bg-white/[0.025] text-slate-400 hover:border-cyan-300/30 hover:text-white"
            }`}
          >
            {label}
          </Link>
        );
      })}
    </nav>
  );
}
