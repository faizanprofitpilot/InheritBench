# Licensing

## Repository

InheritBench is licensed under Apache-2.0 in `LICENSE`.

## Day 1 Models

| Role | Model | Pinned revision | Reviewed license | Access |
|---|---|---|---|---|
| Source | `Qwen/Qwen2.5-0.5B-Instruct` | `7ae557604adf67be50417f59c2c2f167def9a775` | Apache-2.0 | Public |
| Target | `allenai/OLMo-2-0425-1B-Instruct` | `48d788eca847d4d7548f375ad03d3c9312f6139e` | Apache-2.0 | Public |
| Fallback | `HuggingFaceTB/SmolLM2-1.7B-Instruct` | `31b70e2e869a7173562077fd711b654946d38674` | Apache-2.0 | Public |

Review sources:

- <https://huggingface.co/Qwen/Qwen2.5-0.5B-Instruct>
- <https://huggingface.co/allenai/OLMo-2-0425-1B-Instruct>
- <https://huggingface.co/HuggingFaceTB/SmolLM2-1.7B-Instruct>

The model configuration files record the exact revision, access status, license status, and model
card URL. Runtime metadata inspection validates the pinned files and architecture claim without
silently changing the manual review fields.

## Repository Exclusions

Model weights, tokenizer caches, Hugging Face tokens, Modal credentials, `.env` files, and local
cache directories are not committed. Public model use remains subject to each upstream license and
model card.

## Day 2 Adapters

Day 2 creates LoRA adapter weights derived from the pinned Apache-2.0 Qwen and OLMo bases. Adapter
weights and checkpoints remain ignored locally under `adapters/day2`; they are not committed to Git.
Only the three selected final adapters are eligible for deterministic GitHub Release packaging:

- `source_adapted_full-8242bcea6f327545`
- `target_full_retrain-fd1966615c845dab`
- `target_limited_retrain_10pct-c2e5ec18f58ba342`

Each release archive includes its adapter config, safetensors, README, and machine-readable lineage.
Users must obtain the corresponding pinned base model separately and remain subject to its license.

## Day 3 Teacher and Adapter

Day 3 verifies the Day 2 Qwen source adapter from the public `day2-v0.1.0` release before teacher
inference. The frozen archive hash is
`8ee07058b71056bf7119582eb15f9fee4febf20b60f8942efa470be44b84a007`; every internal adapter file
must also match the immutable Day 2 release-verification artifact.

No Day 3 OLMo adapter was produced because the synthetic-data acceptance gate failed before
training. Consequently no `day3-v0.1.0` release was created. Any future selected Day 3 adapter would
remain ignored under `adapters/day3`; Qwen and OLMo remain subject to their reviewed Apache-2.0
licenses.
