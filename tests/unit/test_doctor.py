from inheritbench.doctor import DoctorCheck, aggregate_status


def _check(status: str, blocking: bool) -> DoctorCheck:
    return DoctorCheck.model_validate(
        {
            "id": "test",
            "status": status,
            "blocking": blocking,
            "message": "message",
            "details": {},
            "remediation": None,
        },
        strict=True,
    )


def test_doctor_aggregation() -> None:
    assert aggregate_status([_check("PASS", True)]) == "PASS"
    assert aggregate_status([_check("WARN", False)]) == "WARN"
    assert aggregate_status([_check("FAIL", False)]) == "WARN"
    assert aggregate_status([_check("FAIL", True)]) == "FAIL"
