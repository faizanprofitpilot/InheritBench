"use client";

import type { SystemSummary } from "@/lib/data-schema";

import { MetricChart } from "@/components/metric-chart";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

export function SurfaceExplorer({ systems }: { systems: SystemSummary[] }) {
  return (
    <Tabs defaultValue="confirmatory">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <TabsList aria-label="Evaluation surface">
          <TabsTrigger value="confirmatory">Confirmatory · n=64</TabsTrigger>
          <TabsTrigger value="adversarial">Adversarial · n=32</TabsTrigger>
        </TabsList>
        <p className="text-sm text-slate-500">Separate frozen surfaces. No blended score.</p>
      </div>
      <TabsContent value="confirmatory">
        <MetricChart systems={systems} surface="confirmatory" />
      </TabsContent>
      <TabsContent value="adversarial">
        <MetricChart systems={systems} surface="adversarial" />
      </TabsContent>
    </Tabs>
  );
}
