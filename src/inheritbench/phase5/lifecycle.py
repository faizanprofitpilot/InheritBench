"""Phase 5 local product and deployment lifecycle."""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Any, cast

from inheritbench.artifacts.hashing import canonical_json_bytes, content_sha256
from inheritbench.artifacts.store import write_atomic_bundle
from inheritbench.phase5 import (
    PHASE4_DECISION_CONTENT_SHA256,
    PHASE5_SHOWCASE_CONTENT_SHA256,
)
from inheritbench.phase5.projection import PROJECTION_ROOT, REPO_ROOT, verify_web_projection
from inheritbench.phase5.schemas import (
    Phase5DeploymentVerificationV0_1,
    Phase5ProductDecisionV0_1,
    Phase5WebBuildManifestV0_1,
)

_EXCLUDED = {"content_sha256", "created_at", "finished_at"}
BUILD_MANIFEST = REPO_ROOT / (
    "artifacts/phase5/web-build/inheritbench-web-build-v0.1/manifest.json"
)
DECISION_ROOT = REPO_ROOT / "artifacts/phase5/product-decisions"
DEPLOYMENT_ROOT = REPO_ROOT / "artifacts/phase5/deployment-verifications"


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return cast(dict[str, Any], value)


def _content(value: Any) -> str:
    return content_sha256(value, excluded_keys=_EXCLUDED)


def finalize_local_product(build_manifest_path: Path = BUILD_MANIFEST) -> Path:
    projection = verify_web_projection()
    build_manifest = Phase5WebBuildManifestV0_1.model_validate(_load(build_manifest_path))
    if _content(build_manifest) != build_manifest.content_sha256:
        raise ValueError("web build manifest content hash mismatch")
    if build_manifest.projection_content_sha256 != projection.content_sha256:
        raise ValueError("web build used a different projection")
    if build_manifest.showcase_content_sha256 != PHASE5_SHOWCASE_CONTENT_SHA256:
        raise ValueError("web build used a different showcase")
    payload: dict[str, Any] = {
        "schema_version": "phase5-product-decision-v0.1",
        "decision_id": "phase5-product-local-v0.1",
        "product_status": "PHASE5_PRODUCT_COMPLETED_LOCAL_ONLY",
        "deployment_status": "DEPLOYMENT_REQUIRED",
        "projection_content_sha256": projection.content_sha256,
        "showcase_content_sha256": PHASE5_SHOWCASE_CONTENT_SHA256,
        "phase4_decision_content_sha256": PHASE4_DECISION_CONTENT_SHA256,
        "web_build_manifest_sha256": build_manifest.content_sha256,
        "deployment_verification_sha256": None,
        "public_url": None,
        "historical_artifacts_modified": False,
    }
    payload["content_sha256"] = _content(payload)
    decision = Phase5ProductDecisionV0_1.model_validate(payload)
    return write_atomic_bundle(
        DECISION_ROOT,
        decision.decision_id,
        {"decision.json": canonical_json_bytes(decision) + b"\n"},
    )


def verify_deployment(url: str) -> Path:
    if not url.startswith("https://"):
        raise ValueError("deployment verification requires a stable HTTPS URL")
    with tempfile.TemporaryDirectory(prefix="inheritbench-phase5-deployment-") as directory:
        report = Path(directory) / "deployment-verification.json"
        environment = dict(os.environ)
        environment["DEPLOYMENT_URL"] = url.rstrip("/")
        environment["PHASE5_DEPLOYMENT_REPORT"] = str(report)
        subprocess.run(
            [
                "pnpm",
                "--filter",
                "@inheritbench/web",
                "exec",
                "playwright",
                "test",
                "e2e/deployment.spec.ts",
            ],
            cwd=REPO_ROOT,
            env=environment,
            check=True,
        )
        verification = Phase5DeploymentVerificationV0_1.model_validate(_load(report))
        if verification.public_url.rstrip("/") != url.rstrip("/"):
            raise ValueError("deployment report URL mismatch")
        if _content(verification) != verification.content_sha256:
            raise ValueError("deployment verification content hash mismatch")
        return write_atomic_bundle(
            DEPLOYMENT_ROOT,
            verification.verification_id,
            {"verification.json": canonical_json_bytes(verification) + b"\n"},
        )


def finalize_deployment(verification_path: Path) -> Path:
    projection = verify_web_projection(PROJECTION_ROOT / "inheritbench-web-v0.1")
    build_manifest = Phase5WebBuildManifestV0_1.model_validate(_load(BUILD_MANIFEST))
    verification = Phase5DeploymentVerificationV0_1.model_validate(_load(verification_path))
    if _content(verification) != verification.content_sha256:
        raise ValueError("deployment verification content hash mismatch")
    payload: dict[str, Any] = {
        "schema_version": "phase5-product-decision-v0.1",
        "decision_id": "phase5-product-deployed-v0.1",
        "product_status": "PHASE5_PRODUCT_COMPLETED",
        "deployment_status": "DEPLOYED_VERIFIED",
        "projection_content_sha256": projection.content_sha256,
        "showcase_content_sha256": PHASE5_SHOWCASE_CONTENT_SHA256,
        "phase4_decision_content_sha256": PHASE4_DECISION_CONTENT_SHA256,
        "web_build_manifest_sha256": build_manifest.content_sha256,
        "deployment_verification_sha256": verification.content_sha256,
        "public_url": verification.public_url,
        "historical_artifacts_modified": False,
    }
    payload["content_sha256"] = _content(payload)
    decision = Phase5ProductDecisionV0_1.model_validate(payload)
    return write_atomic_bundle(
        DECISION_ROOT,
        decision.decision_id,
        {"decision.json": canonical_json_bytes(decision) + b"\n"},
    )
