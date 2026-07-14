from pathlib import Path

from inheritbench.blockers.subsets import build_subset_manifests


def test_blocker_subsets_are_split_safe_and_balanced() -> None:
    validation, training = build_subset_manifests(Path("data/opsroute/v0.1.0"))

    assert validation.source_split == "validation"
    assert len(validation.example_ids) == 8
    assert training.source_split == "train"
    assert len(training.example_ids) == 32
    assert not set(validation.example_ids) & set(training.example_ids)
    assert all("fixture_" not in example_id for example_id in validation.example_ids)
    assert all("_00_" in example_id or "_01_" in example_id for example_id in training.example_ids)
