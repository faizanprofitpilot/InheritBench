# Seeded Reference Succession Protocol Amendment

Amendment ID: `seeded-reference-succession-v0.1`

The original direct-parity gate required exact behavioral reproduction of a historical direct adapter. Post-run diagnosis established that the historical trainer attached randomly initialized LoRA parameters before applying its declared seed and preserved neither the initial adapter state nor the relevant MPS RNG state. Exact reconstruction of that adapter is therefore impossible from the immutable evidence.

The historical result, failed parity gate, and stop decision remain unchanged. Future product-reference runs use the corrected seeded protocol, which records initialization identity, RNG-state hashes, schedule, encoding, checkpoints, evaluation facts, and exported adapter identity.

This prospective amendment does not change the capability pack, evaluation records, teacher outputs, authorized anchor pool, training-token budget, checkpoint policy, readiness thresholds, confirmatory surface, adversarial surface, or safety gates.

The corrected direct protocol must first reproduce itself under an independent execution. Behavioral reproduction requires exact supervision, schedule, encoding, initial adapter identity, raw predictions, evaluator facts, safety findings, and readiness. Ordered loss and gradient telemetry use the prospectively frozen MPS tolerance `abs_tol=1e-6`, `rel_tol=1e-5`; learning rates remain exact. Bitwise reproducibility is reported separately.

Only after seeded direct behavioral reproduction succeeds may the real generic anchored succession run. The anchored successor is judged against the previously declared readiness contract. Historical Phase 3B behavioral parity is a secondary comparison, not an unattainable prerequisite based on unrecorded random initialization.

The anchored plan binds the complete authorized anchor pool. Individual anchors are selected only after the generic engine evaluates teacher outputs, derives coverage deficits, and enters `ANCHORS_REQUIRED`.

Because this execution explicitly prohibits commits, the machine-readable amendment is content-addressed against the repository `HEAD` and dirty-worktree digest. It is not represented as Git preregistration.
