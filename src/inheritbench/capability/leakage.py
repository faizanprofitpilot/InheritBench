"""Task-neutral duplicate and leakage checks."""

from __future__ import annotations

from collections import defaultdict

from inheritbench.capability.schemas import CapabilityInputRecord


def leakage_collisions(
    corpora: dict[str, list[CapabilityInputRecord]],
) -> dict[str, list[tuple[str, str, str]]]:
    collisions: dict[str, list[tuple[str, str, str]]] = {
        "record_id": [],
        "content": [],
        "semantic": [],
    }
    seen: dict[str, dict[str, tuple[str, str]]] = {key: {} for key in collisions}
    for corpus_name in sorted(corpora):
        for record in corpora[corpus_name]:
            values = {
                "record_id": record.record_id,
                "content": record.content_sha256,
                "semantic": record.semantic_signature,
            }
            for collision_type, value in values.items():
                prior = seen[collision_type].get(value)
                if prior is not None and prior[0] != corpus_name:
                    collisions[collision_type].append(
                        (value, f"{prior[0]}:{prior[1]}", f"{corpus_name}:{record.record_id}")
                    )
                else:
                    seen[collision_type][value] = (corpus_name, record.record_id)
    return collisions


def duplicate_ids(records: list[CapabilityInputRecord]) -> list[str]:
    counts: defaultdict[str, int] = defaultdict(int)
    for record in records:
        counts[record.record_id] += 1
    return sorted(record_id for record_id, count in counts.items() if count > 1)
