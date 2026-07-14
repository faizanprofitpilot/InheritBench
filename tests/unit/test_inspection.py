from pathlib import Path

from inheritbench.config import load_model_config
from inheritbench.models.inspection import InspectedModel, _shape_comparisons


def _model(shapes: dict[str, list[list[int]]]) -> InspectedModel:
    return InspectedModel(
        model_id="example/model",
        revision="a" * 40,
        expected_architecture_class="ExampleForCausalLM",
        architecture_class="ExampleForCausalLM",
        model_type="example",
        parameter_count=10,
        hidden_size=8,
        num_hidden_layers=2,
        num_attention_heads=2,
        num_key_value_heads=1,
        vocabulary_size=100,
        maximum_position_embeddings=1024,
        tie_word_embeddings=False,
        tokenizer_class="ExampleTokenizer",
        chat_template_available=True,
        special_token_ids={"bos_token_id": 1, "eos_token_id": 2, "pad_token_id": 2},
        linear_modules={},
        target_module_shapes=shapes,
    )


def test_projection_shape_mismatch_and_missing_module() -> None:
    source_config = load_model_config(Path("configs/models/source.yaml"))
    source = _model({suffix: [[8, 8]] for suffix in source_config.intended_lora_target_modules})
    target = _model(
        {
            "q_proj": [[16, 8]],
            "k_proj": [],
            "v_proj": [[8, 8]],
            "o_proj": [[8, 8]],
        }
    )
    comparison = _shape_comparisons(source_config, source, target)
    assert comparison["q_proj"] is False
    assert comparison["k_proj"] is False
    assert comparison["v_proj"] is True
