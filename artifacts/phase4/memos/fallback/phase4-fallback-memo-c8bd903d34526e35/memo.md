# InheritBench Adversarial Transfer Evidence Memo

## Executive Summary

- The confirmatory evidence separates viable adapted targets from the untouched target. Evidence: `confirmatory_strict:target_untouched`, `confirmatory_strict:target_full_retrain`, `confirmatory_strict:target_limited_retrain_10pct`, `confirmatory_strict:target_hybrid_anchored_distillation_10`.

## Transfer Assessment

- The anchored hybrid target leads the confirmatory semantic comparison among target candidates. Evidence: `confirmatory_semantic:target_untouched`, `confirmatory_semantic:target_full_retrain`, `confirmatory_semantic:target_limited_retrain_10pct`, `confirmatory_semantic:target_hybrid_anchored_distillation_10`.

## Adversarial Weaknesses

- Adversarial evaluation exposes system-specific contract and safety failures that remain visible in the evidence matrices. Evidence: `adversarial_semantic:target_untouched`, `adversarial_semantic:target_full_retrain`, `adversarial_semantic:target_limited_retrain_10pct`, `adversarial_semantic:target_hybrid_anchored_distillation_10`.

## Tradeoffs

- The hybrid condition uses both direct anchors and teacher labels and also inherits upstream teacher cost. Evidence: `direct_original_labels:target_hybrid_anchored_distillation_10`, `upstream_original_labels:target_hybrid_anchored_distillation_10`, `hybrid_accounting:teacher_generation_processed_tokens`, `hybrid_accounting:source_teacher_training_tokens`, `hybrid_accounting:original_anchor_labels_used_by_target`, `hybrid_accounting:synthetic_labels_used_by_target`.

## Migration Recommendations

- `minimum_direct_labels` → `target_hybrid_anchored_distillation_10`: The frozen profile ordering determines this result without a weighted score. Evidence: `migration_profile:minimum_direct_labels`.
- `maximum_confirmed_capability` → `target_hybrid_anchored_distillation_10`: The frozen profile ordering determines this result without a weighted score. Evidence: `migration_profile:maximum_confirmed_capability`.
- `maximum_adversarial_resilience` → `target_full_retrain`: The frozen profile ordering determines this result without a weighted score. Evidence: `migration_profile:maximum_adversarial_resilience`.
- `minimum_complexity` → `target_full_retrain`: The frozen profile ordering determines this result without a weighted score. Evidence: `migration_profile:minimum_complexity`.
- `no_source_teacher` → `target_full_retrain`: The frozen profile ordering determines this result without a weighted score. Evidence: `migration_profile:no_source_teacher`.
- `original_labels_unavailable` → `NO_VIABLE_TRAINED_MIGRATION`: The frozen profile ordering determines this result without a weighted score. Evidence: `migration_profile:original_labels_unavailable`.

## Limitations

- Results apply only to the pinned Qwen and OLMo revisions, OpsRoute v0.1.0, and seed 20260714.
- One seed establishes replayability but does not establish statistical significance.
- The adversarial evaluation was not used for tuning or method selection.

## Next Steps

- Use the validated evidence bundle as the input contract for Phase 5 without starting new scientific variants.
- Preserve the exact evaluation surfaces when presenting migration recommendations.

## Evidence Values

- `adversarial_semantic:target_full_retrain` = `0.6875` from `artifacts/phase4/analysis/phase4-analysis-98cdc9db978646e7/analysis.json` `$.matrices[2].semantic_exact`
- `adversarial_semantic:target_hybrid_anchored_distillation_10` = `0.625` from `artifacts/phase4/analysis/phase4-analysis-98cdc9db978646e7/analysis.json` `$.matrices[3].semantic_exact`
- `adversarial_semantic:target_limited_retrain_10pct` = `0.40625` from `artifacts/phase4/analysis/phase4-analysis-98cdc9db978646e7/analysis.json` `$.matrices[4].semantic_exact`
- `adversarial_semantic:target_untouched` = `0.0` from `artifacts/phase4/analysis/phase4-analysis-98cdc9db978646e7/analysis.json` `$.matrices[5].semantic_exact`
- `confirmatory_semantic:target_full_retrain` = `0.796875` from `artifacts/phase4/migration-profiles/phase4-migration-5817e9c8736549e4/profiles.json` `$.rows[3].confirmatory_semantic`
- `confirmatory_semantic:target_hybrid_anchored_distillation_10` = `0.859375` from `artifacts/phase4/migration-profiles/phase4-migration-5817e9c8736549e4/profiles.json` `$.rows[5].confirmatory_semantic`
- `confirmatory_semantic:target_limited_retrain_10pct` = `0.65625` from `artifacts/phase4/migration-profiles/phase4-migration-5817e9c8736549e4/profiles.json` `$.rows[4].confirmatory_semantic`
- `confirmatory_semantic:target_untouched` = `0.0` from `artifacts/phase4/migration-profiles/phase4-migration-5817e9c8736549e4/profiles.json` `$.rows[2].confirmatory_semantic`
- `confirmatory_strict:target_full_retrain` = `1.0` from `artifacts/phase4/migration-profiles/phase4-migration-5817e9c8736549e4/profiles.json` `$.rows[3].confirmatory_strict`
- `confirmatory_strict:target_hybrid_anchored_distillation_10` = `1.0` from `artifacts/phase4/migration-profiles/phase4-migration-5817e9c8736549e4/profiles.json` `$.rows[5].confirmatory_strict`
- `confirmatory_strict:target_limited_retrain_10pct` = `0.90625` from `artifacts/phase4/migration-profiles/phase4-migration-5817e9c8736549e4/profiles.json` `$.rows[4].confirmatory_strict`
- `confirmatory_strict:target_untouched` = `0.0` from `artifacts/phase4/migration-profiles/phase4-migration-5817e9c8736549e4/profiles.json` `$.rows[2].confirmatory_strict`
- `direct_original_labels:target_hybrid_anchored_distillation_10` = `10` from `artifacts/phase4/migration-profiles/phase4-migration-5817e9c8736549e4/profiles.json` `$.rows[5].direct_original_labels`
- `hybrid_accounting:original_anchor_labels_used_by_target` = `10` from `artifacts/phase3b/hybrid-data/phase3b-hybrid-dataset-3a77845a67e42af3/manifest.json` `$.accounting.original_anchor_labels_used_by_target`
- `hybrid_accounting:source_teacher_training_tokens` = `379768` from `artifacts/phase3b/hybrid-data/phase3b-hybrid-dataset-3a77845a67e42af3/manifest.json` `$.accounting.source_teacher_training_tokens`
- `hybrid_accounting:synthetic_labels_used_by_target` = `214` from `artifacts/phase3b/hybrid-data/phase3b-hybrid-dataset-3a77845a67e42af3/manifest.json` `$.accounting.synthetic_labels_used_by_target`
- `hybrid_accounting:teacher_generation_processed_tokens` = `323601` from `artifacts/phase3b/hybrid-data/phase3b-hybrid-dataset-3a77845a67e42af3/manifest.json` `$.accounting.teacher_generation_processed_tokens`
- `migration_profile:maximum_adversarial_resilience` = `"target_full_retrain"` from `artifacts/phase4/migration-profiles/phase4-migration-5817e9c8736549e4/profiles.json` `$.recommendations[2].recommendation`
- `migration_profile:maximum_confirmed_capability` = `"target_hybrid_anchored_distillation_10"` from `artifacts/phase4/migration-profiles/phase4-migration-5817e9c8736549e4/profiles.json` `$.recommendations[1].recommendation`
- `migration_profile:minimum_complexity` = `"target_full_retrain"` from `artifacts/phase4/migration-profiles/phase4-migration-5817e9c8736549e4/profiles.json` `$.recommendations[3].recommendation`
- `migration_profile:minimum_direct_labels` = `"target_hybrid_anchored_distillation_10"` from `artifacts/phase4/migration-profiles/phase4-migration-5817e9c8736549e4/profiles.json` `$.recommendations[0].recommendation`
- `migration_profile:no_source_teacher` = `"target_full_retrain"` from `artifacts/phase4/migration-profiles/phase4-migration-5817e9c8736549e4/profiles.json` `$.recommendations[4].recommendation`
- `migration_profile:original_labels_unavailable` = `"NO_VIABLE_TRAINED_MIGRATION"` from `artifacts/phase4/migration-profiles/phase4-migration-5817e9c8736549e4/profiles.json` `$.recommendations[5].recommendation`
- `upstream_original_labels:target_hybrid_anchored_distillation_10` = `224` from `artifacts/phase4/migration-profiles/phase4-migration-5817e9c8736549e4/profiles.json` `$.rows[5].upstream_original_labels`
