import * as React from "react";

import { cn } from "@/lib/utils";

export function Card({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div
      className={cn(
        "rounded-2xl border border-white/10 bg-slate-950/65 shadow-[0_24px_80px_rgba(2,8,23,0.34)] backdrop-blur",
        className,
      )}
      {...props}
    />
  );
}
