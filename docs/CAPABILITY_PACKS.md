# Capability Packs

A capability pack is the versioned contract for one model-succession job. It identifies the learned
behavior, source and target models, evaluator versions, safety vocabulary, supported transfer method,
publication, and product limitations.

## OpsRoute v0.1.0

```text
capabilities/opsroute/v0.1.0/
├── capability.yaml
├── policy_registry.json
├── safety_rules.yaml
└── README.md
```

The first pack covers refund policy routing and subscription cancellation/retention for the pinned
Qwen → OLMo case.

## Declarative Fields

`capability.yaml` declares:

- capability identity and support status;
- task config and hash;
- source and target IDs, revisions, config paths, and hashes;
- scenario families and archetypes;
- prompt, parser, and evaluator versions;
- supported execution modes;
- Anchored Behavioral Transfer as the supported strategy;
- recovered adapter ID, release tag, archive name, bytes, SHA-256, and URL;
- explicit product limitations.

`policy_registry.json` closes the allowed policy/reason vocabulary for future pack validation.
`safety_rules.yaml` versions clean and adversarial readiness requirements.

## Code-Defined Behavior

The pack does not replace implementation. In v0.1, these remain code-defined:

- OpsRoute input and contract schemas;
- deterministic policy resolution;
- surface generation and leakage signatures;
- model-specific supervised formatting and LoRA training;
- parser `0.1.0` and evaluator `v0`;
- replay aggregation and readiness-rule implementation;
- static web presentation.

Historical `ActionContract` validation accepted any nonempty policy code. Exact scoring still detected
incorrect aliases. Future capability packs should enforce registry-backed vocabularies at validation
time; historical evidence remains unchanged.

## Current Support Boundary

The pack is not a public plug-in API. v0.1 does not accept arbitrary uploads or user-defined model
pairs. A future pack would need:

1. strict schemas and deterministic policy labels;
2. frozen train, validation, test, and adversarial surfaces;
3. value-sensitive leakage signatures;
4. pinned source and target model support;
5. explicit supervision and training method contracts;
6. versioned readiness and safety rules;
7. immutable evaluation and replay artifacts;
8. a verified deliverable successor artifact;
9. a static, content-addressed product projection.

Adding a directory alone does not provide those guarantees.

## Long-Term Direction

The intended abstraction is model-agnostic but evidence-bound:

> Recover the capability when possible, and condition or block migration when the evidence is
> insufficient.

Generalized capability authoring, arbitrary model loading, hosted training, and one-command
cross-family execution remain future work.
