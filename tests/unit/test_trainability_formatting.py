import re
from pathlib import Path
from typing import Any

import torch

from inheritbench.blockers.trainability import MicroLoraConfig, _encode_training_example
from inheritbench.data.opsroute.generate import load_examples
from inheritbench.models.loader import LoadedModel


class TrainingTokenizer:
    def __init__(self) -> None:
        self.tokens: list[str] = []

    def apply_chat_template(
        self,
        messages: list[dict[str, str]],
        *,
        tokenize: bool,
        add_generation_prompt: bool,
    ) -> str:
        assert tokenize is False
        prefix = "".join(f"<{message['role']}>{message['content']}" for message in messages[:2])
        if add_generation_prompt:
            return prefix + "<assistant>"
        return prefix + f"<assistant>{messages[2]['content']}<eos>"

    def __call__(
        self,
        text: str,
        *,
        add_special_tokens: bool,
        return_tensors: str | None = None,
    ) -> dict[str, Any]:
        assert add_special_tokens is False
        pieces = re.findall(r"<[^>]+>|[A-Za-z0-9_]+|[^\s]", text)
        token_ids: list[int] = []
        for piece in pieces:
            if piece not in self.tokens:
                self.tokens.append(piece)
            token_ids.append(self.tokens.index(piece))
        if return_tensors == "pt":
            return {
                "input_ids": torch.tensor([token_ids]),
                "attention_mask": torch.ones((1, len(token_ids)), dtype=torch.long),
            }
        return {"input_ids": token_ids}

    def decode_ids(self, token_ids: list[int]) -> str:
        return " ".join(self.tokens[token_id] for token_id in token_ids)


def test_training_format_masks_prompt_and_keeps_expected_contract() -> None:
    example = load_examples(
        Path("data/opsroute/v0.1.0"),
        ["opsroute_v010_refund_pending_payment_00_4200d719"],
    )[0]
    tokenizer = TrainingTokenizer()
    loaded = LoadedModel(model=None, tokenizer=tokenizer, device="cpu", dtype="float32")

    batch = _encode_training_example(loaded, example, "0.1.0")

    labels = batch["labels"][0]
    first_supervised = int((labels != -100).nonzero()[0])
    assert first_supervised > 0
    assert torch.all(labels[:first_supervised] == -100)
    supervised_text = tokenizer.decode_ids(labels[first_supervised:].tolist())
    assert "decision" in supervised_text
    assert "no_action" in supervised_text
    assert supervised_text.endswith("<eos>")


def test_second_lora_configuration_remains_bounded() -> None:
    assert MicroLoraConfig(epochs=6).epochs == 6
