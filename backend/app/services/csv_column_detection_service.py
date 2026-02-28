import json
from dataclasses import dataclass
from uuid import uuid4

from app.agents.agent_manager import agent_manager
from app.file_processing.csv_column_mapping import CsvColumnMappingResult
from app.schemas.history_ingest import DetectedCsvColumns


@dataclass(slots=True)
class CsvColumnDetectionResult:
    detected_columns: DetectedCsvColumns | None
    used_llm: bool
    error_code: str | None = None
    error_message: str | None = None


class CsvColumnDetectionService:
    def __init__(
        self,
        agent_manager_instance=agent_manager,
        workflow_name: str = "csv_column_detection_agent",
    ) -> None:
        self._agent_manager = agent_manager_instance
        self._workflow_name = workflow_name

    async def detect_columns(
        self,
        headers: list[str],
        sample_rows: list[dict[str, str]],
        deterministic_result: CsvColumnMappingResult,
    ) -> CsvColumnDetectionResult:
        if deterministic_result.is_complete:
            return CsvColumnDetectionResult(
                detected_columns=DetectedCsvColumns(
                    question_col=deterministic_result.question_col or "",
                    answer_col=deterministic_result.answer_col or "",
                    domain_col=deterministic_result.domain_col or "",
                ),
                used_llm=False,
            )

        prompt = self._build_prompt(headers, sample_rows[:5], deterministic_result)

        try:
            session_id = f"csv-column-detection-{uuid4()}"
            agent = self._agent_manager.get_agent(
                session_id,
                workflow_name=self._workflow_name,
            )
            response = await agent.chat(prompt)
            payload = json.loads(response)
            detected_columns = DetectedCsvColumns(
                question_col=payload["question_col"],
                answer_col=payload["answer_col"],
                domain_col=payload["domain_col"],
            )
            self._validate_detected_columns(detected_columns, headers)
        except Exception as exc:
            return CsvColumnDetectionResult(
                detected_columns=None,
                used_llm=True,
                error_code="column_mapping_failed",
                error_message=str(exc),
            )

        return CsvColumnDetectionResult(
            detected_columns=detected_columns,
            used_llm=True,
        )

    def _build_prompt(
        self,
        headers: list[str],
        sample_rows: list[dict[str, str]],
        deterministic_result: CsvColumnMappingResult,
    ) -> str:
        return (
            "You are identifying CSV columns for QA ingestion.\n"
            "Return strict JSON only with keys question_col, answer_col, domain_col.\n"
            f"Headers: {json.dumps(headers, ensure_ascii=True)}\n"
            f"Sample rows (max 5): {json.dumps(sample_rows, ensure_ascii=True)}\n"
            f"Unresolved targets: {json.dumps(deterministic_result.unresolved_targets)}\n"
            f"Ambiguous targets: {json.dumps(deterministic_result.ambiguous_targets)}\n"
        )

    def _validate_detected_columns(
        self,
        detected_columns: DetectedCsvColumns,
        headers: list[str],
    ) -> None:
        valid_headers = set(headers)
        for value in [
            detected_columns.question_col,
            detected_columns.answer_col,
            detected_columns.domain_col,
        ]:
            if not value or value not in valid_headers:
                raise ValueError(f"Invalid detected CSV column: {value}")
