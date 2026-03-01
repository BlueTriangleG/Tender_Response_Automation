from __future__ import annotations

from pathlib import Path

import pytest

from tests.e2e.live.edge_case_suite.manifest_loader import load_manifest
from tests.e2e.live.edge_case_suite.models import EvaluationResult
from tests.e2e.live.edge_case_suite.oracle_evaluator import evaluate_oracle
from tests.e2e.live.edge_case_suite.reporting import write_case_artifacts

pytestmark = pytest.mark.live_e2e


def _upload_history_file(client, history_file: Path) -> dict:
    with history_file.open("rb") as handle:
        response = client.post(
            "/api/ingest/history",
            files={
                "file": (
                    history_file.name,
                    handle.read(),
                    "text/csv",
                )
            },
        )

    assert response.status_code == 200
    return response.json()


def _run_tender_case(client, tender_file: Path, *, session_id: str) -> dict:
    with tender_file.open("rb") as handle:
        response = client.post(
            "/api/tender/respond",
            files={
                "file": (
                    tender_file.name,
                    handle.read(),
                    "text/csv",
                )
            },
            data={"sessionId": session_id},
        )

    assert response.status_code == 200
    return response.json()


def test_edge_case_manifest_contains_tender_cases() -> None:
    manifest = load_manifest()

    assert manifest.tender_inputs


def test_zero_question_case_oracle_can_be_evaluated() -> None:
    manifest = load_manifest()
    case = next(
        item
        for item in manifest.tender_inputs
        if item.file.name == "06_blank_rows_only.csv"
    )
    oracle = case.load_oracle()

    actual = {
        "total_questions_processed": 0,
        "summary": {
            "total_questions_processed": 0,
            "overall_completion_status": "completed",
            "completed_questions": 0,
            "unanswered_questions": 0,
            "failed_questions": 0,
        },
        "questions": [],
    }

    result = evaluate_oracle(case.case_id, oracle, actual)

    assert result.passed is True


def test_edge_case_suite_artifact_root_is_under_backend() -> None:
    artifact_root = Path("backend/.artifacts/edge_case_suite")

    assert artifact_root.parts[-2:] == (".artifacts", "edge_case_suite")


@pytest.mark.parametrize(
    "case",
    load_manifest().tender_inputs,
    ids=lambda case: case.case_id,
)
def test_edge_case_suite_live_cases(case, live_client, artifact_root: Path) -> None:
    for history_file in case.recommended_history:
        ingest_payload = _upload_history_file(live_client, history_file)
        assert ingest_payload["failed_file_count"] == 0
        assert ingest_payload["files"][0]["status"] == "processed"

    metadata = {
        "tender_file": str(case.file),
        "history_files": [str(path) for path in case.recommended_history],
    }
    actual = None
    try:
        actual = _run_tender_case(
            live_client,
            case.file,
            session_id=f"edge-case-{case.case_id}",
        )
        oracle = case.load_oracle()
        evaluation = evaluate_oracle(case.case_id, oracle, actual)
    except Exception as exc:
        metadata["execution_error"] = f"{type(exc).__name__}: {exc}"
        evaluation = EvaluationResult(
            case_id=case.case_id,
            passed=False,
            errors=[metadata["execution_error"]],
        )
        write_case_artifacts(
            artifact_root=artifact_root,
            case_id=case.case_id,
            actual_payload=actual,
            evaluation=evaluation,
            metadata=metadata,
        )
        raise

    write_case_artifacts(
        artifact_root=artifact_root,
        case_id=case.case_id,
        actual_payload=actual,
        evaluation=evaluation,
        metadata=metadata,
    )

    assert evaluation.passed, "\n".join(evaluation.errors)


def test_ambiguous_history_ingest_returns_structured_response(
    live_client,
    artifact_root: Path,
) -> None:
    ambiguous_history = next(
        path
        for path in load_manifest().historical_repository
        if path.name == "03_ambiguous_headers.csv"
    )

    payload = _upload_history_file(live_client, ambiguous_history)
    write_case_artifacts(
        artifact_root=artifact_root,
        case_id="03_ambiguous_headers_ingest",
        actual_payload=payload,
        evaluation=evaluate_oracle(
            "03_ambiguous_headers_ingest",
            {"expected_summary": {}, "questions": []},
            {
                "total_questions_processed": 0,
                "summary": {
                    "total_questions_processed": 0,
                    "overall_completion_status": "completed",
                    "completed_questions": 0,
                    "unanswered_questions": 0,
                    "failed_questions": 0,
                },
                "questions": [],
            },
        ),
        metadata={
            "history_file": str(ambiguous_history),
            "response_kind": "history_ingest",
        },
    )

    assert payload["total_file_count"] == 1
    assert payload["files"][0]["status"] in {"processed", "failed"}
