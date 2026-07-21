# Demo Script

Target duration: **2 minutes 58 seconds**. Record the deployed static product only after the
deployment checklist passes. Until then, rehearse with the local static export.

Use original or licensed media, clear narration, and captions. Do not imply that the browser trains
or runs Qwen or OLMo.

## 0:00–0:22 — Problem

**Screen:** Landing hero and replacement-risk panel.

**Narration:**

> Companies replace models for cost, latency, licensing, or infrastructure reasons and can silently
> lose behavior their application depends on. InheritBench finds what broke, helps recover it, and
> proves whether the replacement is ready to ship.

**Overlay:** `Move the model. Keep the capability. Prove it survived.`

## 0:22–0:38 — Workflow

**Screen:** Diagnose → Recover → Assure.

**Narration:**

> Diagnose the capability loss, recover the missing behavior under control, and apply explicit
> evaluation and safety rules before migration.

## 0:38–1:08 — Run the Assurance Lab

**Screen:** `/sandbox/`.

**Actions:**

1. Point to Choose → Run → Review.
2. Select **Untouched OLMo** and run the diagnostic.
3. Point out that no readiness verdict is issued.
4. Select **Anchored successor** and run the evaluation.

**Narration:**

> The browser verifies the committed files, evaluates precomputed predictions, aggregates required
> behaviors, checks safety, applies readiness, and generates local verification details. Model
> training and inference remain precomputed.

## 1:08–1:33 — Show the Decision

**Screen:** Anchored-successor result.

**Narration:**

> Candidate zero recovered all 64 clean operational behaviors. Exact-contract fidelity is 63 of 64,
> strict validity is 64 of 64, and clean safety blockers are zero. The adversarial test still found
> two safety failures on one record, so the unchanged rules return Conditional Pass.

**Overlay:**

```text
Operational correctness  64 / 64
Exact-contract fidelity  63 / 64
Strict validity          64 / 64
Safety findings          2 on 1 adversarial record
Readiness                CONDITIONAL_PASS
```

Do not say “production safe,” “universal transfer,” or “browser inference.”

## 1:33–1:55 — Challenge the Result

**Screen:** Stress section.

**Actions:** Apply **Approval bypass · apply and rerun**.

**Narration:**

> Now I introduce a controlled approval bypass. The same evaluator and readiness rules run again,
> the modified result stays separate from verified evidence, and migration is blocked.

**Overlay:** `Same rules · changed evidence · MIGRATION_BLOCKED`

## 1:55–2:25 — Inspect the Completed Succession

**Screen:** `/run/opsroute-qwen-olmo/`.

**Narration:**

> The inspector explains what changed, what failed, how ten targeted examples repaired the coverage
> gap, why the final result is conditional, and why the candidate selection can be trusted.
> Candidate ranking used validation only; final evaluation ran once after selection.

**Actions:** Show the five at-a-glance questions, candidate comparison, final result, and replay
proof. Open one evidence disclosure briefly.

## 2:25–2:45 — Evidence and AI Collaboration

**Screen:** Evidence page, GPT memo, then repository.

**Narration:**

> Deterministic code owns metrics, safety findings, and readiness. GPT-5.6 explains validated
> evidence; it does not create scores or override gates. Codex helped implement the architecture,
> evaluators, parity tests, numerical investigation, Assurance Lab, and release audit.

**Overlay:** `GPT-5.6 and Codex built the tool; Qwen and OLMo are the succession models.`

## 2:45–2:58 — Closing

**Screen:** Landing page and the two product paths.

**Narration:**

> Test the assurance engine, then inspect the completed Qwen-to-OLMo succession. Move the model. Keep
> the capability. Prove it survived.

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
