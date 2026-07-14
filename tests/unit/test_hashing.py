import hashlib

from inheritbench.artifacts.hashing import canonical_json_bytes, content_sha256, input_ids_sha256


def test_canonical_json_vector() -> None:
    payload = {"z": "café", "a": [2, 1]}
    expected = b'{"a":[2,1],"z":"caf\xc3\xa9"}'
    assert canonical_json_bytes(payload) == expected
    assert content_sha256(payload) == hashlib.sha256(expected).hexdigest()


def test_input_ids_use_fixed_width_signed_bytes() -> None:
    expected = hashlib.sha256((1).to_bytes(8, "big", signed=True)).hexdigest()
    assert input_ids_sha256([1]) == expected
