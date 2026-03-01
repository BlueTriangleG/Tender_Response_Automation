"""Artifact writing for live edge-case E2E runs."""

from __future__ import annotations

import csv
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from tests.e2e.live.edge_case_suite.models import EvaluationResult

SUITE_RESULTS_FILENAME = "suite-results.csv"
SUITE_RESULTS_FIELDS = [
    "recorded_at",
    "case_id",
    "response_kind",
    "passed",
    "error_count",
    "errors",
    "execution_error",
    "total_questions_processed",
    "completed_questions",
    "unanswered_questions",
    "failed_questions",
    "flagged_high_risk_or_inconsistent_responses",
    "overall_completion_status",
    "tender_file",
    "history_file_count",
    "history_files",
    "actual_artifact",
    "report_artifact",
]


def _build_suite_results_row(
    *,
    artifact_root: Path,
    case_id: str,
    recorded_at: str,
    actual_payload: dict[str, Any] | None,
    evaluation: EvaluationResult,
    metadata: dict[str, Any],
) -> dict[str, str]:
    summary = (actual_payload or {}).get("summary", {})
    history_files = metadata.get("history_files", [])
    if not isinstance(history_files, list):
        history_files = []

    return {
        "recorded_at": recorded_at,
        "case_id": case_id,
        "response_kind": str(metadata.get("response_kind", "tender_response")),
        "passed": str(evaluation.passed),
        "error_count": str(len(evaluation.errors)),
        "errors": " | ".join(evaluation.errors),
        "execution_error": str(metadata.get("execution_error", "")),
        "total_questions_processed": str(
            (actual_payload or {}).get("total_questions_processed", "")
        ),
        "completed_questions": str(summary.get("completed_questions", "")),
        "unanswered_questions": str(summary.get("unanswered_questions", "")),
        "failed_questions": str(summary.get("failed_questions", "")),
        "flagged_high_risk_or_inconsistent_responses": str(
            summary.get("flagged_high_risk_or_inconsistent_responses", "")
        ),
        "overall_completion_status": str(summary.get("overall_completion_status", "")),
        "tender_file": str(metadata.get("tender_file", "")),
        "history_file_count": str(len(history_files)),
        "history_files": " | ".join(str(path) for path in history_files),
        "actual_artifact": f"{case_id}.actual.json",
        "report_artifact": f"{case_id}.report.json",
    }


def _write_suite_results_csv(
    *,
    artifact_root: Path,
    row: dict[str, str],
) -> None:
    csv_path = artifact_root / SUITE_RESULTS_FILENAME
    existing_rows: list[dict[str, str]] = []
    if csv_path.exists():
        with csv_path.open(encoding="utf-8", newline="") as handle:
            existing_rows = list(csv.DictReader(handle))

    updated_rows = [
        existing for existing in existing_rows if existing.get("case_id") != row["case_id"]
    ]
    updated_rows.append(row)
    updated_rows.sort(key=lambda item: item["case_id"])

    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=SUITE_RESULTS_FIELDS)
        writer.writeheader()
        writer.writerows(updated_rows)


def write_case_artifacts(
    *,
    artifact_root: Path,
    case_id: str,
    actual_payload: dict[str, Any] | None,
    evaluation: EvaluationResult,
    metadata: dict[str, Any],
) -> None:
    """Write actual output and evaluation results for one case."""

    artifact_root.mkdir(parents=True, exist_ok=True)
    recorded_at = datetime.now(UTC).isoformat()
    enriched_actual = {
        "metadata": {
            **metadata,
            "recorded_at": recorded_at,
        },
        "response": actual_payload,
    }
    (artifact_root / f"{case_id}.actual.json").write_text(
        json.dumps(enriched_actual, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    (artifact_root / f"{case_id}.report.json").write_text(
        json.dumps(
            {
                "metadata": metadata,
                "evaluation": evaluation.as_dict(),
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    _write_suite_results_csv(
        artifact_root=artifact_root,
        row=_build_suite_results_row(
            artifact_root=artifact_root,
            case_id=case_id,
            recorded_at=recorded_at,
            actual_payload=actual_payload,
            evaluation=evaluation,
            metadata=metadata,
        ),
    )
