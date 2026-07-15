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

## Blocker-Resolution Measurements

- All micro-LoRA runs used Apple MPS, float32 training, batch size 1, accumulation 4, and sequential
  model residency.
- Qwen two-epoch run: 1,081,344 trainable of 495,114,112 total parameters; 16 optimizer steps;
  25.97 seconds measured training duration.
- OLMo two-epoch run: 2,097,152 trainable of 1,487,013,888 total parameters; 16 optimizer steps;
  63.73 seconds measured training duration.
- OLMo six-epoch run: 48 optimizer steps; 136.93 seconds measured training duration; post-training
  MPS driver allocation snapshot 15,068,872,704 bytes. PyTorch MPS exposed no peak allocator metric,
  so peak memory is recorded as `null` in the corrected artifact schema.
- Earlier two-epoch artifacts mislabeled the post-training driver allocation snapshot as a peak.
  They remain immutable; `artifacts/blocker-resolution/corrections/correction-8f21fbaa169460c8`
  records the clarification.

### Modal Next Action

The blocker is an external data-export approval imposed before Modal launch. After explicitly
approving workspace-code export to Modal, run:

```bash
uv run inheritbench compute modal-smoke --gpu L4 --output-root artifacts/modal
```

Return the new immutable Modal JSON artifact or complete terminal output to Codex. The existing
blocked record remains preserved and does not count as a GPU attempt.

## Day 2 Measured Local Compute

All Day 2 training used float32 MPS, batch size 1, accumulation 4, linear warmup/decay, rank-8
Q/K/V/O LoRA, and sequential model residency. Validation and test used float16 MPS.

| Method | Steps | Tokens | Training seconds | Trainable parameters |
|---|---:|---:|---:|---:|
| Adapted source | 224 | 379,768 | 437.86 | 1,081,344 |
| Full target | 168 | 272,643 | 617.31 | 2,097,152 |
| Limited target | 168 | 272,634 | 635.43 | 2,097,152 |

The primary source attempt stopped at step 150 after 339.83 seconds under the gradient-norm kill
switch. Its corrected restart completed from base at learning rate `1e-4`.

Largest observed allocation snapshots were 2,077,498,880 current / 11,469,422,592 driver bytes for
source, 5,977,088,768 / 17,393,532,928 for full target, and 5,976,194,304 / 9,569,845,248 for limited
target. These are explicitly allocation snapshots, not peak-memory measurements.

Modal remained unused. Completed local experiments were not migrated or repeated for provider
symmetry.

## Day 3 Compute Contract

- Teacher generation loads pinned Qwen plus the publicly verified Day 2 source adapter in float16
  on MPS, batch size 1, greedy decoding, and at most 256 new tokens.
- Synthetic target training loads untouched pinned OLMo in float32 on MPS with batch size 1,
  accumulation 4, rank-8 Q/K/V/O LoRA, clipping 1.0, and linear warmup/decay.
- Validation and the single held-out test load one fresh float16 OLMo base at a time.
- The whole-sequence schedule stops before 272,643 tokens and records the residual; examples are
  never truncated to hit a numeric budget.
- Telemetry names MPS current and driver allocation snapshots accurately. It does not claim a peak
  measurement unavailable from the backend.
- Modal remains unused and is not required for scientific or distribution completion.

### Day 3 Measured Teacher Compute

| Phase | Candidates | Prompt tokens | Completion tokens | Processed tokens | Active seconds |
|---|---:|---:|---:|---:|---:|
| Initial | 512 | 196,900 | 24,855 | 221,755 | 728.85 |
| Expansion | 256 | 98,430 | 10,293 | 108,723 | 362.80 |
| Total | 768 | 295,330 | 35,148 | 330,478 | 1,091.65 |

Both runs used float16 MPS, batch size 1, greedy decoding, and zero infrastructure retries. The
terminal synthetic-data gate failed before target training, so target training, validation, test,
adapter packaging, and publication consumed no Day 3 compute.
