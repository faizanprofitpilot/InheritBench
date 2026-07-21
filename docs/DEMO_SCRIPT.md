# Demo Script

Target duration: **2 minutes 52 seconds**. Record the deployed static product only after the
deployment checklist passes. Until then, rehearse with the local static export.

Use original or licensed media, clear narration, and captions. Do not imply that the browser trains
or runs Qwen or OLMo.

## 0:00–0:28 — Fine-Tuned Capability Portability

**Screen:** Landing hero and replacement-risk panel.

**Narration:**

> Companies replace models for cost, latency, privacy, licensing, or infrastructure. But the
> capability they fine-tuned into the old model does not automatically move. A replacement can
> still sound intelligent while losing policies, tool contracts, approvals, or safety behavior.
> Satya Nadella has described a reverse information paradox: as intelligence becomes abundant, the
> enterprise learning loop becomes more valuable. InheritBench helps developers retain ownership of
> what they taught their models.

**Overlay:** `Move the model. Keep the capability. Prove it survived.`

Do not present the Nadella sentence as a direct quotation or imply endorsement.

## 0:28–1:02 — Developer CLI Workflow

**Screen:** Landing `#developer-workflow`. Show the capability-pack tree, then the validate, plan,
run, inspect, replay, and export cards.

**Narration:**

> InheritBench is a local CLI. A developer authors a capability pack with model-visible examples,
> evaluator-only expected contracts, schemas, vocabularies, safety rules, coverage groups, optional
> anchors, and readiness thresholds. The CLI validates that pack and freezes a content-addressed
> plan for the supported source, target, and recovery strategy. It verifies the adapted source,
> measures target loss, trains the target adapter, selects using validation only, opens sealed final
> records after selection, applies readiness, exports and reloads the adapter, and preserves replay
> evidence. If supervision coverage is insufficient, the run can pause at ANCHORS_REQUIRED, accept
> explicitly authorized examples, and resume without regenerating completed teacher evidence.

**Visual commands:**

```bash
uv run inheritbench capability validate capabilities/opsroute/v0.2.0
uv run inheritbench succession plan ...
uv run inheritbench succession run --plan runs/<run-id> --device mps
uv run inheritbench succession inspect --run runs/<run-id> --json -
uv run inheritbench succession replay --run runs/<run-id> --output runs/replays
```

## 1:02–1:32 — Completed Qwen → OLMo Succession

**Screen:** `/run/opsroute-qwen-olmo/`. Show model lineage, target loss, recovery candidates,
validation-only selection, final decision, and replay proof.

**Narration:**

> This inspector is proof that the CLI completed a real succession. The source was adapted
> Qwen2.5-0.5B; the replacement was OLMo-2-1B from another architecture. Untouched OLMo lost the
> capability. Direct recovery undercovered important cases, so anchored recovery added ten targeted
> original examples. Four seeded candidates completed. Candidate zero was selected using validation
> only, while the final tests remained sealed. The adapter was exported, verified on a fresh OLMo
> load, and replay passed across 192 predictions.

**Overlay:**

```text
Clean operational correctness   64 / 64
Clean exact-contract fidelity   63 / 64
Clean strict validity           64 / 64
Clean safety blockers           0
Adversarial exact-contract result 20 / 32
Adversarial strict validity     31 / 32
Safety findings                 2 findings on 1 record
Readiness                       CONDITIONAL_PASS
Replay                          192 predictions verified
```

Do not say “production safe,” “universal transfer,” or “browser inference.”

## 1:32–2:08 — Judge-Testable Assurance

**Screen:** `/sandbox/`.

**Actions:**

1. Point to the “not the model-migration engine” boundary.
2. Run **Untouched OLMo** and show diagnostic-only `0 / 32`.
3. Run **Anchored successor** and show `CONDITIONAL_PASS`.
4. Apply **Approval bypass · apply and rerun**.
5. Show the changed record and `CONDITIONAL_PASS → MIGRATION_BLOCKED`.
6. Reset the original.

**Narration:**

> The Lab is not performing the migration or running Qwen or OLMo. The CLI produced these
> predictions. The browser verifies their integrity, evaluates contracts and coverage, checks
> safety, applies readiness, and creates an unsigned local receipt. Untouched OLMo gets no fabricated
> readiness verdict because final surfaces are absent. The anchored successor returns Conditional
> Pass. Now I change one real prediction in browser memory to bypass approval. The same evaluator
> and readiness contract recompute the result, and migration becomes blocked.

**Overlay:** `Same rules · changed prediction · CONDITIONAL_PASS → MIGRATION_BLOCKED`

## 2:08–2:34 — Evidence and Boundaries

**Screen:** Inspector replay proof, evidence page, then landing boundary section.

**Narration:**

> Capability packs are generic for the supported structured-JSON profile, but real model execution
> is intentionally narrow: the pinned Qwen-to-OLMo registry, demonstrated on Apple MPS, with OpsRoute
> as the only real trained capability. Purchase Approval is fixture-only. The anchored reference
> uses verified frozen teacher outputs; live generic teacher generation is not yet proven.
> InheritBench does not guarantee recovery or production safety. It can correctly return Migration
> Blocked.

## 2:34–2:48 — Codex and GPT-5.6

**Screen:** GPT memo, repository, and “Built with Codex and GPT-5.6.”

**Narration:**

> Codex helped implement the engine, experimental controls, evaluator and readiness infrastructure,
> numerical-guard repair, Python-to-TypeScript parity, evidence projection, tests, and audits.
> GPT-5.6 produced a structured memo from validated evidence. Deterministic code still owns every
> score and gate. Qwen and OLMo are the succession models.

## 2:48–2:55 — Closing

**Screen:** Landing hero and public URL.

**Narration:**

> InheritBench turns model choice into controlled model succession. Move the model. Keep the
> capability. Prove it survived.

## Recording Checklist

- [ ] Public URL is accessible in an incognito Chromium window.
- [ ] `/sandbox/` and `/run/opsroute-qwen-olmo/` survive direct navigation and refresh.
- [ ] No browser console, hydration, or document-overflow error appears.
- [ ] Untouched OLMo remains diagnostic-only.
- [ ] Anchored successor shows the exact documented metrics.
- [ ] Approval-bypass mutation produces `MIGRATION_BLOCKED`.
- [ ] Reset restores the verified reference result.
- [ ] Captions distinguish browser evaluation from precomputed training and inference.
- [ ] Clean and adversarial metrics remain separate.
- [ ] GPT-5.6 and Codex roles are described accurately.
- [ ] No third-party copyrighted media is used without permission.
- [ ] Final duration is under three minutes.
