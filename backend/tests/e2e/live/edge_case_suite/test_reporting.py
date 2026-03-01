from __future__ import annotations

import csv
import json
from pathlib import Path

from tests.e2e.live.edge_case_suite.models import EvaluationResult
from tests.e2e.live.edge_case_suite.reporting import write_case_artifacts


def test_write_case_artifacts_creates_suite_results_csv(tmp_path: Path) -> None:
    write_case_artifacts(
        artifact_root=tmp_path,
        case_id="demo-case",
        actual_payload={
            "total_questions_processed": 2,
            "summary": {
                "total_questions_processed": 2,
                "completed_questions": 1,
                "unanswered_questions": 1,
                "failed_questions": 0,
                "flagged_high_risk_or_inconsistent_responses": 1,
                "overall_completion_status": "completed_with_flags",
            },
            "questions": [],
        },
        evaluation=EvaluationResult(
            case_id="demo-case",
            passed=False,
            errors=["first issue", "second issue"],
        ),
        metadata={
            "tender_file": "/tmp/demo.csv",
            "history_files": ["/tmp/history-a.csv", "/tmp/history-b.csv"],
        },
    )

    with (tmp_path / "suite-results.csv").open(encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    assert len(rows) == 1
    assert rows[0]["case_id"] == "demo-case"
    assert rows[0]["passed"] == "False"
    assert rows[0]["overall_completion_status"] == "completed_with_flags"
    assert rows[0]["flagged_high_risk_or_inconsistent_responses"] == "1"
    assert rows[0]["history_file_count"] == "2"
    assert rows[0]["errors"] == "first issue | second issue"


def test_write_case_artifacts_records_execution_errors_without_response(tmp_path: Path) -> None:
    write_case_artifacts(
        artifact_root=tmp_path,
        case_id="crashed-case",
        actual_payload=None,
        evaluation=EvaluationResult(
            case_id="crashed-case",
            passed=False,
            errors=["request crashed before assertion"],
        ),
        metadata={
            "tender_file": "/tmp/crashed.csv",
            "execution_error": "AttributeError: summary was None",
        },
    )

    with (tmp_path / "suite-results.csv").open(encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    actual_json = json.loads((tmp_path / "crashed-case.actual.json").read_text(encoding="utf-8"))

    assert len(rows) == 1
    assert rows[0]["case_id"] == "crashed-case"
    assert rows[0]["passed"] == "False"
    assert rows[0]["execution_error"] == "AttributeError: summary was None"
    assert rows[0]["overall_completion_status"] == ""
    assert actual_json["response"] is None
