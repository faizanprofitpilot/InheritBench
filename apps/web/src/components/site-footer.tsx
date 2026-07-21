import Link from "next/link";

export function SiteFooter() {
  return (
    <footer className="border-t border-white/8 py-10">
      <div className="mx-auto flex max-w-7xl flex-col gap-3 px-4 text-sm text-slate-500 sm:px-6 md:flex-row md:items-center md:justify-between lg:px-8">
        <p>InheritBench makes capability recovery and migration assurance executable.</p>
        <div className="flex flex-wrap gap-5">
          <Link
            href="/sandbox/"
            className="rounded-sm hover:text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-300"
          >
            Assurance Lab
          </Link>
          <Link
            href="/run/opsroute-qwen-olmo/"
            className="rounded-sm hover:text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-300"
          >
            Reference run
          </Link>
          <Link
            href="/lab/opsroute/evidence"
            className="rounded-sm hover:text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-300"
          >
            Integrity
          </Link>
          <a
            href="https://github.com/faizanprofitpilot/InheritBench"
            className="rounded-sm hover:text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-300"
          >
            Repository
          </a>
        </div>
      </div>
    </footer>
  );
}
