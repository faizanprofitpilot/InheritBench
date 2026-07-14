from inheritbench.logging import redact_secrets


def test_secret_redaction_is_recursive() -> None:
    redacted = redact_secrets(
        None,
        "info",
        {"event": "test", "HF_TOKEN": "secret", "nested": {"password": "secret"}},
    )
    assert redacted["HF_TOKEN"] == "[REDACTED]"
    assert redacted["nested"]["password"] == "[REDACTED]"
