# Day 1 Decisions

## 2026-07-14 — Reproducible Foundation

- Use CPython 3.11.15 with `requires-python >=3.11,<3.12`.
- Use `uv` and commit `uv.lock`; do not fall back to the system Python or another package manager.
- Use PEP 621, Hatchling, a `src/` package, Typer, Pydantic v2, PyYAML, Rich, and structlog.
- Install PyTorch/Transformers and Modal through separate extras. Defer PEFT, Datasets, TRL,
  scikit-learn, and bitsandbytes until work that requires them begins.
- Logs go to stderr; command JSON goes to stdout or an explicit artifact path.
- Environment variables are documented but never automatically loaded or committed.

## 2026-07-14 — Model Pair

- Source: `Qwen/Qwen2.5-0.5B-Instruct` at
  `7ae557604adf67be50417f59c2c2f167def9a775`.
- Target: `allenai/OLMo-2-0425-1B-Instruct` at
  `48d788eca847d4d7548f375ad03d3c9312f6139e`.
- Fallback target: `HuggingFaceTB/SmolLM2-1.7B-Instruct` at
  `31b70e2e869a7173562077fd711b654946d38674`.
- All are configured for `trust_remote_code=false`, native chat templates, no quantization, eager
  attention, and a 1,024-token prompt ceiling.
- Heterogeneity and direct adapter-reuse verdicts are separate. Structural mismatch does not imply
  that every heterogeneous transfer method is impossible.

## 2026-07-14 — OpsRoute v0.1

- Use exactly refund routing and subscription cancellation/retention.
- Use seed `20260714`; task, generator, template, prompt, and contract version `0.1.0`.
- Generate 320 examples: 224 train, 32 validation, 32 test, and 32 adversarial.
- Generate labels only through pure policy resolvers with the documented precedence rules.
- Use SHA-256-derived per-record sub-seeds and reject ID, surface, or semantic collisions.
- Fixture IDs begin with `fixture_`; fixture evidence cannot enter benchmark manifests or inference.

## 2026-07-14 — Parsing and Metrics

- Accept strict whole-output JSON and one whole-output Markdown JSON fence only.
- Forbid first-object extraction, trailing-comma repair, case/alias normalization, JSON5, field
  invention, prose reconstruction, and LLM repair.
- Report unweighted strict validity, exact semantic contract match, atomic correctness, and safety
  metrics. Do not introduce a weighted Operational Contract Score on Day 1.
- Treat parser-invalid generations as completed inference with zero correctness and explicit
  unknown safety values where no decision is observable.

## 2026-07-14 — Prompt Revision 0.1.1

- The original `0.1.0` smoke run produced no schema-valid OLMo target output.
- Use the one allowed simplified revision: an exact six-key JSON skeleton, explicit JSON-null
  instruction, family-specific policy/reason mappings, and exact tool argument names.
- The revision changes only the rendered prompt contract. It does not expose evaluator-owned labels,
  alter examples, or change split membership.
- OLMo produced no schema-valid output under either `0.1.0` or `0.1.1`; activate the predeclared
  SmolLM2 fallback. Preserve `configs/tasks/opsroute_prompt_v0.1.1.yaml` and use the original
  `0.1.0` prompt for the fallback attempt so source validity remains demonstrated.
- SmolLM2 also produced no schema-valid output under either prompt. Stop model-pair selection under
  the declared kill switch and mark Day 1 blocked rather than weakening the parser or selecting
  results post hoc.

## 2026-07-14 — Evidence and Compute

- Serialize canonical JSON with sorted keys, compact separators, UTF-8, and `allow_nan=false`.
- Finalize datasets and run bundles atomically and never overwrite them.
- Create new run/replay IDs for reruns even if nonvolatile content hashes match.
- Run models sequentially on local MPS first. Use one bounded Modal L4 metadata probe without model
  downloads; record honest `BLOCKED` evidence if it cannot run.
- The Modal invocation was rejected before execution by the external data-export approval gate. Do
  not circumvent that control; record zero attempts and no remote environment instead.
