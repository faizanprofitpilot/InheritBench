import { GeistMono } from "geist/font/mono";
import { GeistSans } from "geist/font/sans";
import type { Metadata } from "next";

import { SiteFooter } from "@/components/site-footer";
import { SiteHeader } from "@/components/site-header";

import "./globals.css";

export const metadata: Metadata = {
  title: { default: "InheritBench Model Succession Engine", template: "%s · InheritBench" },
  description:
    "A local CLI for diagnosing fine-tuned capability loss, recovering a supported successor, and producing replayable migration evidence.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" className="dark">
      <body
        className={`${GeistSans.variable} ${GeistMono.variable} min-h-screen bg-slate-950 text-slate-100 antialiased`}
      >
        <SiteHeader />
        <main>{children}</main>
        <SiteFooter />
      </body>
    </html>
  );
}
