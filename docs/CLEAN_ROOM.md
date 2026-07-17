# Clean-Room Statement

InheritBench Day 1 is a new implementation created from the repository's product specification and
the approved Day 1 build plan. It does not reproduce a research paper, copy benchmark scoring logic,
or present an approximation under a published method name.

The implementation uses public package APIs and public model metadata. Dataset scenarios, policy
resolvers, prompts, parser behavior, metrics, schemas, tests, and artifact contracts were written for
this project. No external benchmark labels, private data, model weights, credentials, or generated
test labels are committed.

Later work must preserve this separation: evaluated models may produce predictions, but evaluator-
owned expected contracts and hidden split membership remain deterministic Python artifacts.

Day 2 training schedules, limited-data selection, safety gate, checkpoint selection, replay,
comparison, and deterministic release packaging are likewise new project implementation.

Day 3 candidate templates, value-sensitive leakage signatures, teacher filtering, scheduling,
status decisions, and replay logic are newly implemented for InheritBench. Public model and adapter
artifacts are consumed only through pinned identifiers and verified hashes; no upstream benchmark
logic or private dataset content is copied.

The distribution-matched recovery is also newly implemented. It derives a statistical fingerprint
from this repository's committed train inputs, uses deterministic Hamilton apportionment, and reuses
the project's own frozen rendering and leakage contracts. It does not copy an external dataset,
benchmark method, or private label source.

Phase 3B anchored transfer, confirmatory generation, Git-tree preregistration, mixed-origin schedule,
evaluation matrix, replay, and publication contracts are original InheritBench implementation. The
ten anchors come only from this repository's frozen deterministic train split; no external benchmark
data, hidden labels, or copied transfer method is introduced.

Phase 4 adversarial analysis, evidence graph, claim validator, migration profiles, and Phase 5
projection and succession replay are also project-specific implementations. The static product reads
only committed InheritBench evidence and the project's verified public adapter record. Codex assisted
implementation, testing, and documentation; the founder defined the product problem, scientific
protocols, bounded interventions, accounting requirements, readiness interpretation, and product
truth boundaries.
