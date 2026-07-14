# Day 1 Compute Plan

## Measured Local Environment

- macOS 26.5.2 on arm64.
- Apple M2 Pro with 10 CPU cores and 16 GPU cores.
- 32 GB unified memory.
- Approximately 276 GiB free storage at assessment time.
- Primary accelerator path: Apple MPS. CUDA is not available locally.

`inheritbench doctor` captures the execution-time environment, package versions, disk, RAM, and
accelerator availability in `artifacts/day1/doctor.json`.

## Guardrails

- Load source and target sequentially; never keep both resident.
- Use batch size 1, greedy decoding, a 1,024-token prompt ceiling, and 256 new tokens.
- Use no quantization and no training on Day 1.
- Unload each model, run garbage collection, and clear the active backend cache before continuing.
- Never silently truncate policy or context.
- Record OOM, timeout, and model errors as failed predictions and a failed run.

## Planning Estimates

| Model | Repository weight estimate | Inference peak estimate |
|---|---:|---:|
| Qwen2.5-0.5B | ~0.99 GB | 2–4 GiB |
| OLMo2-1B | ~2.97 GB | 5–8 GiB |
| SmolLM2-1.7B fallback | ~3.42 GB | 6–10 GiB |

These are planning estimates, not measured claims. Inspection and run artifacts supersede them.

## Modal

The Day 1 Modal command requests one L4 for a CUDA/BF16/package/storage metadata probe. It downloads
no model and creates no persistent volume, training function, provider abstraction, or orchestration
system. Modal cost is external and is not assumed to be covered by OpenAI credits. A failed probe is
recorded as `BLOCKED`; it is never represented as a zero benchmark score.

### Observed Modal Status

The execution environment rejected the L4 invocation before any remote function ran because sending
workspace code to a third-party service was not approved. The immutable artifact
`artifacts/modal/modal-smoke-20260714T192115-de421316.json` records `BLOCKED`, zero attempts, no
remote metadata, and no GPU allocation. No workaround was attempted.
