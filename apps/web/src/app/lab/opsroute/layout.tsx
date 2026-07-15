import Link from "next/link";

const sections = [
  ["Overview", "/lab/opsroute"],
  ["Methods", "/lab/opsroute/methods"],
  ["Failures", "/lab/opsroute/failures"],
  ["GPT memo", "/lab/opsroute/memo"],
  ["Evidence", "/lab/opsroute/evidence"],
];

export default function OpsRouteLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="mx-auto max-w-7xl px-4 py-12 sm:px-6 lg:px-8">
      <nav aria-label="OpsRoute sections" className="mb-12 flex gap-2 overflow-x-auto border-b border-white/8 pb-4">
        {sections.map(([label, href]) => (
          <Link
            key={href}
            href={href}
            className="whitespace-nowrap rounded-full border border-white/10 bg-white/[0.025] px-4 py-2 text-sm text-slate-400 transition hover:border-cyan-300/30 hover:text-white"
          >
            {label}
          </Link>
        ))}
      </nav>
      {children}
    </div>
  );
}
