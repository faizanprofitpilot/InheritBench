from pathlib import Path

from inheritbench.data.opsroute.generate import (
    build_dataset_artifacts,
    check_dataset,
    generate_examples,
    write_dataset,
)


def test_dataset_is_reproducible_and_split_isolated(task_config, tmp_path: Path) -> None:
    first = build_dataset_artifacts(task_config)
    second = build_dataset_artifacts(task_config)
    assert first == second

    examples = generate_examples(task_config)
    assert len(examples) == 320
    assert len({example.example_id for example in examples}) == 320
    assert len({example.semantic_signature for example in examples}) == 320
    counts = {
        split: sum(example.split == split for example in examples)
        for split in ("train", "validation", "test", "adversarial")
    }
    assert counts == {
        "train": 224,
        "validation": 32,
        "test": 32,
        "adversarial": 32,
    }

    output = tmp_path / "v0.1.0"
    written = write_dataset(task_config, output)
    checked = check_dataset(task_config, output)
    assert checked.dataset_sha256 == written.dataset_sha256
