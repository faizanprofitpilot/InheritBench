"use client";

import { motion } from "motion/react";

import { Card } from "@/components/ui/card";
import type { Story } from "@/lib/data-schema";

export function StoryRail({ story }: { story: Story }) {
  const facts = new Map(story.facts.map((fact) => [fact.fact_id, fact]));
  return (
    <div className="grid gap-4 lg:grid-cols-5">
      {story.stages.map((stage, index) => (
        <motion.div
          key={stage.stage_id}
          initial={{ opacity: 0, y: 14 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: "-60px" }}
          transition={{ duration: 0.35, delay: index * 0.04 }}
        >
          <Card className="h-full p-5">
            <p className="font-mono text-xs text-cyan-300">0{index + 1}</p>
            <p className="mt-5 text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">
              {stage.eyebrow}
            </p>
            <h3 className="mt-3 text-lg font-semibold leading-6 text-white">{stage.title}</h3>
            <p className="mt-3 text-sm leading-6 text-slate-400">{stage.summary}</p>
            <div className="mt-6 space-y-3 border-t border-white/8 pt-4">
              {stage.fact_ids.slice(0, 3).map((factId) => {
                const fact = facts.get(factId);
                return fact ? (
                  <div key={factId}>
                    <p className="font-mono text-lg font-semibold text-cyan-100">
                      {fact.display_value}
                    </p>
                    <p className="mt-1 text-xs leading-5 text-slate-500">{fact.label}</p>
                  </div>
                ) : null;
              })}
            </div>
          </Card>
        </motion.div>
      ))}
    </div>
  );
}
