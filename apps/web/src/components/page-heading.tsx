import type { ReactNode } from "react";

import { Badge } from "@/components/ui/badge";

export function PageHeading({
  eyebrow,
  title,
  description,
  badge,
  children,
}: {
  eyebrow: string;
  title: string;
  description: string;
  badge?: string;
  children?: ReactNode;
}) {
  return (
    <div className="max-w-4xl">
      <div className="flex flex-wrap items-center gap-3">
        <p className="eyebrow">{eyebrow}</p>
        {badge && <Badge>{badge}</Badge>}
      </div>
      <h1 className="mt-5 text-balance text-4xl font-semibold tracking-tight text-white sm:text-5xl">
        {title}
      </h1>
      <p className="mt-5 max-w-3xl text-balance text-lg leading-8 text-slate-400">{description}</p>
      {children && <div className="mt-7">{children}</div>}
    </div>
  );
}
