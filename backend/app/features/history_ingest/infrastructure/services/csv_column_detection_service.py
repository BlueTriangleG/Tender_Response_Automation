"""Column detection service that combines rule-based and LLM-assisted mapping."""

import json
from dataclasses import dataclass

from app.core.config import settings
from app.features.history_ingest.domain.csv_column_mapping import CsvColumnMappingResult
from app.features.history_ingest.schemas.responses import DetectedCsvColumns
from app.integrations.openai.chat_completions_client import OpenAIChatCompletionsClient


@dataclass(slots=True)
class CsvColumnDetectionResult:
    """Resolved column mapping plus metadata about how detection succeeded or failed."""

    detected_columns: DetectedCsvColumns | None
    used_llm: bool
    error_code: str | None = None
    error_message: str | None = None


class CsvColumnDetectionService:
    """Resolve question/answer/domain columns for uploaded history CSV files."""

    def __init__(
        self,
        completion_client: OpenAIChatCompletionsClient | None = None,
    ) -> None:
        self._completion_client = completion_client or OpenAIChatCompletionsClient(
            model=settings.openai_csv_column_model
        )

    async def detect_columns(
        self,
        headers: list[str],
        sample_rows: list[dict[str, str]],
        deterministic_result: CsvColumnMappingResult,
    ) -> CsvColumnDetectionResult:
        """Use deterministic matching first, then fall back to the LLM if needed."""

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
            response = await self._completion_client.create_json_completion(
                system_prompt="Return strict JSON with keys question_col, answer_col, domain_col.",
                user_prompt=prompt,
            )
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

        return CsvColumnDetectionResult(detected_columns=detected_columns, used_llm=True)

    def _build_prompt(
        self,
        headers: list[str],
        sample_rows: list[dict[str, str]],
        deterministic_result: CsvColumnMappingResult,
    ) -> str:
        """Provide the model with enough context to resolve ambiguous CSV headers."""

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
        """Reject model output that references headers absent from the uploaded CSV."""

        valid_headers = set(headers)
        for value in [
            detected_columns.question_col,
            detected_columns.answer_col,
            detected_columns.domain_col,
        ]:
            if not value or value not in valid_headers:
                raise ValueError(f"Invalid detected CSV column: {value}")
