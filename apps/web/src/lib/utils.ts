import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs));
}

export function percent(value: number): string {
  return `${(value * 100).toFixed(1)}%`;
}

export function labelSystem(systemId: string): string {
  const labels: Record<string, string> = {
    source_base_supporting: "Qwen · base",
    source_adapted_full: "Qwen · adapted",
    target_untouched: "OLMo · untouched",
    target_full_retrain: "OLMo · full retrain",
    target_limited_retrain_10pct: "OLMo · 10.7% labels",
    target_hybrid_anchored_distillation_10: "OLMo · anchored transfer",
  };
  return labels[systemId] ?? systemId.replaceAll("_", " ");
}

export function labelToken(value: string): string {
  return value
    .split("_")
    .map((token) => token.charAt(0).toUpperCase() + token.slice(1))
    .join(" ");
}
