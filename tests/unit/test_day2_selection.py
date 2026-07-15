from inheritbench.day2.schemas import CheckpointScore
from inheritbench.day2.training import _selection_key


def _score(**updates: object) -> CheckpointScore:
    values: dict[str, object] = {
        "checkpoint_id": "checkpoint-a",
        "optimizer_step": 56,
        "evaluation_run_id": "evaluation-a",
        "completed_predictions": 32,
        "semantic_exact": 0.5,
        "strict_valid": 0.75,
        "abstention_accuracy": 0.8,
        "approval_accuracy": 0.8,
        "argument_f1": 0.7,
        "teacher_forced_loss": 0.4,
        "unauthorized_actions": 0,
        "approval_bypasses": 0,
        "false_actions": 0,
        "eligible": True,
        "rejection_reasons": [],
    }
    values.update(updates)
    return CheckpointScore.model_validate(values, strict=True)


def test_semantic_score_precedes_strict_score() -> None:
    semantic = _score(semantic_exact=0.6, strict_valid=0.5)
    strict = _score(checkpoint_id="checkpoint-b", semantic_exact=0.5, strict_valid=1.0)
    assert max([semantic, strict], key=_selection_key) == semantic


def test_lower_loss_then_earlier_step_breaks_ties() -> None:
    lower_loss = _score(checkpoint_id="checkpoint-b", teacher_forced_loss=0.3, optimizer_step=112)
    assert max([_score(), lower_loss], key=_selection_key) == lower_loss
    early = _score()
    late = _score(checkpoint_id="checkpoint-c", optimizer_step=112)
    assert max([late, early], key=_selection_key) == early
