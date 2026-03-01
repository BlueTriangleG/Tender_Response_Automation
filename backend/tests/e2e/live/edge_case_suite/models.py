"""Typed helpers for the live edge-case E2E suite."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[5]
DATASET_ROOT = REPO_ROOT / "test_data" / "edge_case_suite"
ARTIFACT_ROOT = REPO_ROOT / "backend" / ".artifacts" / "edge_case_suite"


@dataclass(slots=True)
class TenderCase:
    """One tender input entry from the edge-case manifest."""

    file: Path
    oracle: Path
    recommended_history: list[Path]

    @property
    def case_id(self) -> str:
        """Return a stable case id derived from the oracle filename."""

        return self.oracle.name.removesuffix(".oracle.json")

    def load_oracle(self) -> dict[str, Any]:
        """Read the oracle JSON for this tender case."""

        import json

        return json.loads(self.oracle.read_text(encoding="utf-8"))


@dataclass(slots=True)
class EdgeCaseManifest:
    """Typed manifest content used by the live E2E runner."""

    historical_repository: list[Path]
    tender_inputs: list[TenderCase]


@dataclass(slots=True)
class EvaluationResult:
    """Result of comparing one actual workflow response against one oracle."""

    case_id: str
    passed: bool
    errors: list[str]

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable representation."""

        return {
            "case_id": self.case_id,
            "passed": self.passed,
            "errors": self.errors,
        }
