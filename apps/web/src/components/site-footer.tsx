import Link from "next/link";

export function SiteFooter() {
  return (
    <footer className="border-t border-white/8 py-10">
      <div className="mx-auto flex max-w-7xl flex-col gap-3 px-4 text-sm text-slate-500 sm:px-6 md:flex-row md:items-center md:justify-between lg:px-8">
        <p>InheritBench · frozen evidence for model succession decisions.</p>
        <div className="flex gap-5">
          <Link href="/lab/opsroute/evidence" className="hover:text-white">
            Integrity
          </Link>
          <a href="https://github.com/faizanprofitpilot/InheritBench" className="hover:text-white">
            Apache-2.0
          </a>
        </div>
      </div>
    </footer>
  );
}
