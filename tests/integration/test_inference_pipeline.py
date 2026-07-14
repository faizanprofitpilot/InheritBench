from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import torch

from inheritbench.artifacts.schemas import EnvironmentState, GitState
from inheritbench.config import load_task_config
from inheritbench.data.opsroute.generate import write_dataset
from inheritbench.inference.runner import replay_run, run_pair_inference
from inheritbench.models.loader import LoadedModel


class FakeTokenizer:
    pad_token_id = 0

    def apply_chat_template(self, messages, *, tokenize, add_generation_prompt):
        assert tokenize is False
        assert add_generation_prompt is True
        return "prompt:" + messages[-1]["content"]

    def __call__(self, prompt, *, return_tensors, add_special_tokens):
        assert prompt
        assert return_tensors == "pt"
        assert add_special_tokens is False
        return {"input_ids": torch.tensor([[1, 2, 3]])}

    def decode(self, token_ids, *, skip_special_tokens):
        assert skip_special_tokens is True
        assert token_ids.tolist() == [4]
        return json.dumps(
            {
                "decision": "no_action",
                "tool": None,
                "arguments": {},
                "approval_required": False,
                "policy_code": "FIN-NOACT-01",
                "reason_code": "NO_REFUND_ACTION_REQUESTED",
            }
        )


class FakeModel:
    generation_config = SimpleNamespace(eos_token_id=4)

    def generate(self, **encoded):
        input_ids = encoded["input_ids"]
        return torch.cat([input_ids, torch.tensor([[4]])], dim=1)


def test_mock_pair_inference_to_replay(monkeypatch, tmp_path: Path) -> None:
    dataset = tmp_path / "data" / "v0.1.0"
    write_dataset(load_task_config(Path("configs/tasks/opsroute.yaml")), dataset)

    monkeypatch.setattr(
        "inheritbench.inference.runner.load_model",
        lambda config, device_override: LoadedModel(
            model=FakeModel(), tokenizer=FakeTokenizer(), device="cpu", dtype="float32"
        ),
    )
    monkeypatch.setattr("inheritbench.inference.runner.unload_model", lambda loaded: None)
    monkeypatch.setattr(
        "inheritbench.inference.runner._loaded_inspection",
        lambda source, target, root, device: SimpleNamespace(
            content_sha256="a" * 64, heterogeneity_verdict="CONFIRMED"
        ),
    )
    monkeypatch.setattr(
        "inheritbench.inference.runner._environment_state",
        lambda: EnvironmentState(
            fingerprint_sha256="b" * 64,
            python="3.11.15",
            packages={},
            os="test",
            hardware={},
        ),
    )
    monkeypatch.setattr(
        "inheritbench.inference.runner._git_state",
        lambda: GitState(commit="c" * 40, worktree_dirty=True, tracked_diff_sha256=None),
    )

    run = run_pair_inference(
        source_path=Path("configs/models/source.yaml"),
        target_path=Path("configs/models/target.yaml"),
        task_path=Path("configs/tasks/opsroute.yaml"),
        examples_path=dataset / "smoke_ids.json",
        device="cpu",
        output_root=tmp_path / "runs",
        command=["inheritbench", "infer"],
    )
    predictions = run.joinpath("predictions.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(predictions) == 8
    assert all(json.loads(line)["status"] == "COMPLETED" for line in predictions)
    assert all(json.loads(line)["prompt_token_count"] == 3 for line in predictions)
    assert all(json.loads(line)["generated_token_count"] == 1 for line in predictions)
    assert all(json.loads(line)["finish_condition"] == "EOS" for line in predictions)

    replay = replay_run(
        run_directory=run,
        output_root=tmp_path / "replays",
        verify_stored=True,
    )
    verification = json.loads(replay.joinpath("verification.json").read_text(encoding="utf-8"))
    assert verification["status"] == "PASSED"
    assert verification["prediction_records_verified"] == 8
