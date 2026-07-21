# Capability Packs

A capability pack is the developer-owned input to the local InheritBench CLI. It defines the learned
capability that must survive a model replacement while keeping model-visible inputs separate from
evaluator-only contracts and final records. Pack v0.2 is task-neutral for the supported
`structured-json-v0.1` profile; it does not make arbitrary model architectures executable.

## Pack v0.2

```text
capability.yaml
schemas/input.schema.json
schemas/output.schema.json
schemas/cross-field.schema.json
evaluator.yaml
prompts/system.txt
vocabularies/decisions.json
vocabularies/tools.json
vocabularies/reason_codes.json
vocabularies/policy_codes.json
rules/safety.yaml
rules/readiness.yaml
data/source_gate.inputs.jsonl
data/direct_train.jsonl
data/transfer_pool.inputs.jsonl
data/validation.inputs.jsonl
data/confirmatory.inputs.jsonl
data/adversarial.inputs.jsonl
oracles/source_gate.jsonl
oracles/transfer_pool.jsonl
oracles/validation.jsonl
oracles/confirmatory.jsonl
oracles/adversarial.jsonl
supervision/frozen_teacher_outputs.jsonl
anchors/available.jsonl
schedules/direct-reference.json
schedules/anchored-reference.json
README.md
```

`capability init` creates this complete layout with `status: DRAFT`. Planning accepts only `READY`
or `REFERENCE`; `FIXTURE_ONLY` execution is available only to hidden tests.

## Authoring Commands

```bash
uv run inheritbench capability init NAME \
  --template structured-json-v0.1 \
  --output PATH

uv run inheritbench capability validate PACK --json -
uv run inheritbench capability inspect PACK --json -
```

Validation rejects unknown fields, unsafe or missing paths, malformed JSON Schemas, invalid record
hashes, duplicate IDs, broken input/oracle joins, invalid controlled-vocabulary values, malformed
safety AST nodes, unconstrained readiness thresholds, duplicate strategy or comparison identities,
bad coverage-group metadata, invalid direct labels, and tampered anchors.

Every finding has a stable code, severity, file, JSON Pointer, optional record ID, message, and
remediation. Executable packs must validate completely before a plan can be frozen.

## Data Separation

Pack records have four distinct roles:

- **Model-visible inputs** contain messages and task facts.
- **Evaluator-only oracles** contain expected contracts and safety context.
- **Direct labels** explicitly authorize original supervision.
- **Anchors** explicitly authorize an intervention after a teacher coverage deficit.

The stage data broker exposes only the minimum authorized handle:

| Stage | Inputs | Oracles or labels |
|---|---|---|
| Source gate | Source-gate inputs | Source-gate oracles |
| Target baseline | Source-gate inputs | Source-gate oracles |
| Teacher generation | Transfer-pool inputs | No oracle handle |
| Teacher filtering | Saved teacher output | Transfer-pool oracles |
| Target training | Frozen labeled records | No evaluation inputs or oracles |
| Checkpoint selection | Validation inputs | Validation oracles |
| Confirmatory | Confirmatory inputs | Confirmatory oracles |
| Adversarial | Adversarial inputs | Adversarial oracles |

Confirmatory and adversarial evaluations are immutable, exactly once, and cannot enter training or
checkpoint selection.

## Declarative Evaluator

`evaluator.yaml` uses RFC 6901 JSON Pointers and supports:

- strict JSON and optional one whole-output JSON fence;
- input/output JSON Schema validation;
- required and ignored pointers;
- exact scalar, object, and list comparisons;
- explicit set comparison;
- exact numeric comparison or declared tolerance;
- per-field correctness;
- structural full-contract exactness;
- semantic contract match;
- closed controlled vocabularies.

Safety rules are data, not executable templates. The typed AST permits only `eq`, `ne`, `in`,
`not_in`, `exists`, `missing`, `contains`, `and`, `or`, and `not`. Pointer-to-pointer operands are
explicit JSON Pointer references. No `eval`, arbitrary expression, or filesystem access exists.

An optional trusted evaluator must be an installed local `inheritbench.evaluators` entry point whose
distribution, version, plugin identity, and module SHA-256 exactly match the pack. Plugins receive
only in-memory input, output, and oracle values and return normalized results. They do not write
artifacts, access final-test paths, select checkpoints, or set readiness.

## Readiness and Strategies

Packs declare constrained numeric thresholds, not final outcomes. The engine derives `PASS`,
`CONDITIONAL_PASS`, or `MIGRATION_BLOCKED`.

Supported strategy IDs:

- `direct-target-lora-v0.1`;
- `anchored-behavioral-transfer-v0.1`.

Training profiles declare the token budget, accumulation, clipping, AdamW parameters, warmup,
sequence limit, LoRA settings, and checkpoint fractions. The model registry—not the pack—owns
architecture classes, exact revisions, tokenizer behavior, dtype policy, and explicit LoRA module
mappings.

## Reference and Fixture

### OpsRoute

`capabilities/opsroute/v0.2.0` is the product-owned reference projection. It preserves capability
identity `opsroute@0.1.0` while converting frozen historical inputs and oracles into task-neutral
pack records. A deterministic projector regenerates it into temporary storage for byte comparison.
Historical OpsRoute files are read-only. The later
`capabilities/opsroute/v0.3.0/evaluation/` confirmatory and adversarial surfaces support the bounded
multi-start product reference; they are sealed evaluation data, not a second authoring format.

### Purchase Approval

`examples/capability-packs/purchase-approval` is a materially different `FIXTURE_ONLY` pack with
different input/output fields, decisions, tools, policy and reason vocabularies, safety predicates,
thresholds, coverage groups, and record counts. It proves that the generic loader, evaluator,
strategies, intervention flow, replay, and browser schema do not depend on OpsRoute literals.

It is test evidence only and is not a model-transfer result.

## Current Support Boundary

The pack interface is generic; the real model registry remains intentionally narrow:

- Qwen2.5 0.5B Instruct at one exact revision;
- OLMo-2 1B Instruct at one exact revision;
- explicit Q/K/V/O LoRA mappings;
- Apple MPS as the executed real backend.

Arbitrary Transformers identities, guessed target modules, remote code, hosted training, and
automatic prompt/model search are unsupported. The Assurance Lab accepts local JSON/JSONL prediction
uploads only when they match the committed capability and record contract; an upload does not add a
new model, train a successor, or make a new capability pack available in the deployed product.

The OpsRoute anchored reference uses verified frozen teacher outputs. Live generic teacher
generation is not yet proven. A valid pack and supported model pair do not guarantee recovery or
production safety; readiness may correctly be `MIGRATION_BLOCKED`.

See [Pack-Driven Succession v0.2](PACK_DRIVEN_SUCCESSION.md) for planning, execution, anchor
intervention, replay, browser import, and real integration evidence.
