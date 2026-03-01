"""Manifest loader for the edge-case live E2E suite."""

from __future__ import annotations

from pathlib import Path

import yaml

from tests.e2e.live.edge_case_suite.models import (
    DATASET_ROOT,
    EdgeCaseManifest,
    TenderCase,
)


def _resolve_dataset_path(relative_path: str) -> Path:
    """Resolve a path declared in the dataset manifest."""

    return (DATASET_ROOT / relative_path).resolve()


def load_manifest() -> EdgeCaseManifest:
    """Load the edge-case manifest into typed Python objects."""

    manifest_path = DATASET_ROOT / "manifest.yaml"
    payload = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))

    historical_repository = [
        _resolve_dataset_path(item["file"])
        for item in payload.get("historical_repository", [])
    ]
    tender_inputs = [
        TenderCase(
            file=_resolve_dataset_path(item["file"]),
            oracle=_resolve_dataset_path(item["oracle"]),
            recommended_history=[
                _resolve_dataset_path(path)
                for path in item.get("recommended_history", [])
            ],
        )
        for item in payload.get("tender_inputs", [])
    ]

    return EdgeCaseManifest(
        historical_repository=historical_repository,
        tender_inputs=tender_inputs,
    )
