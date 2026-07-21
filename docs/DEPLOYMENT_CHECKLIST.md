# Deployment Checklist

Deployment is not complete. The repository status remains:

```text
PHASE5_PRODUCT_COMPLETED_LOCAL_ONLY / DEPLOYMENT_REQUIRED
```

Use this checklist to create and verify the public static product without introducing Python,
models, secrets, or runtime APIs into the hosting build.

## Vercel Project

The committed `vercel.json` defines:

- framework: Next.js;
- install: `pnpm install --frozen-lockfile`;
- build: `pnpm --filter @inheritbench/web build`;
- output: `apps/web/out`.

The Next.js app uses static export and trailing slashes. Project root should remain the repository
root so Node ingestion can read the committed showcase and Phase 5 projection.

## Environment

- Node: `22.14.0`
- pnpm: `10.7.1`
- environment variables: none required
- Python: not required by the deployment build
- uv: not required by the deployment build
- OpenAI/Hugging Face credentials: prohibited and unnecessary
- model weights or adapters: not bundled in the site

## Pre-Deployment Gates

```bash
pnpm install --frozen-lockfile
pnpm ingest
pnpm lint:web
pnpm typecheck:web
pnpm test:web
pnpm build
pnpm --filter @inheritbench/web verify-build-report
```

Complete local verification, including Python projection and browser tests:

```bash
uv sync --frozen --group dev
pnpm verify
```

The separate GitHub Actions `node-only-static-build` job must pass from a clean checkout.

## Public Access

- [ ] Stable HTTPS URL exists.
- [ ] Root route opens in an incognito browser.
- [ ] `/sandbox/` opens directly and after refresh.
- [ ] `/run/opsroute-qwen-olmo/` opens directly and after refresh.
- [ ] All `/lab/opsroute/` deep links open directly.
- [ ] No login, authentication wall, cookie gate, API key, or secret is required.
- [ ] No 404 occurs on trailing-slash routes.
- [ ] No non-static runtime API request is made.

## Product Flow

- [ ] Landing primary action opens `/sandbox/`; **Reference run** opens
      `/run/opsroute-qwen-olmo/`.
- [ ] Assurance Lab starts with Choose → Run → Review and hides results before evaluation.
- [ ] Untouched OLMo is clearly diagnostic-only and receives no readiness verdict.
- [ ] Anchored successor returns `CONDITIONAL_PASS` and the documented exact metrics.
- [ ] Approval-bypass mutation recomputes the decision as `MIGRATION_BLOCKED`.
- [ ] Reset restores the verified reference result.
- [ ] Verification details expose integrity, replay/parity, and an unsigned local receipt.
- [ ] Advanced tools stay collapsed initially; local JSON/JSONL remains in browser memory.
- [ ] Completed inspector explains capability loss, recovery, validation-only selection, final
      conditions, adapter identity, and replay evidence.
- [ ] Historical Phase 4 evidence remains visually distinct from current product evidence.
- [ ] No product copy claims browser training, inference, signature, or external attestation.

## Browser and Accessibility

- [ ] Chromium desktop has no console, hydration, or network errors.
- [ ] Chromium mobile layout has no overflow or hidden critical controls.
- [ ] Keyboard-only navigation reaches all actions and dialogs.
- [ ] Visible focus is preserved.
- [ ] Reduced-motion preference disables decorative transitions.
- [ ] Axe checks pass on all public routes.
- [ ] Charts retain text or table equivalents.
- [ ] Status does not rely on color alone.

Firefox and Safari may be smoke-tested, but they must not be called verified platforms until that
evidence is recorded.

## Security Headers and Data

- [ ] `poweredByHeader` remains disabled.
- [ ] Static security headers are present as configured by the hosting project.
- [ ] No local absolute paths appear in served JSON.
- [ ] Raw model output is escaped text, never injected HTML.
- [ ] External release links use safe attributes.
- [ ] Served showcase, projection, and succession manifests match committed SHA-256 values.
- [ ] Adapter bytes remain on the verified GitHub release rather than in deployment assets.

## Hosted Verification Artifact

After the manual checks pass, run:

```bash
uv run inheritbench phase5 verify-deployment --url https://REPLACE_WITH_PUBLIC_URL
```

Inspect the immutable verification artifact. Then finalize only with that exact artifact:

```bash
uv run inheritbench phase5 finalize-deployment \
  --verification artifacts/phase5/deployment-verifications/REPLACE_WITH_ID/verification.json
```

Use the path actually emitted by `verify-deployment`; do not invent it.

## Completion Criteria

Only successful public verification may change status to:

```text
PHASE5_PRODUCT_COMPLETED / DEPLOYED_VERIFIED
```

Until then, keep `PHASE5_PRODUCT_COMPLETED_LOCAL_ONLY / DEPLOYMENT_REQUIRED` in README, Devpost,
demo script, and product metadata.
