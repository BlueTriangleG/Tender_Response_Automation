from app.features.history_ingest.domain.csv_column_mapping import CsvColumnMappingResult
from app.features.history_ingest.infrastructure.services.csv_column_detection_service import (
    CsvColumnDetectionService,
)
from app.features.history_ingest.schemas.responses import DetectedCsvColumns


class FakeCompletionClient:
    def __init__(self, response: str, should_raise: bool = False) -> None:
        self.response = response
        self.should_raise = should_raise
        self.calls: list[tuple[str, str]] = []

    async def create_json_completion(self, *, system_prompt: str, user_prompt: str) -> str:
        self.calls.append((system_prompt, user_prompt))
        if self.should_raise:
            raise RuntimeError("llm unavailable")
        return self.response


async def test_detect_columns_skips_llm_when_mapping_is_complete() -> None:
    completion_client = FakeCompletionClient('{"question_col":"q","answer_col":"a","domain_col":"d"}')
    service = CsvColumnDetectionService(completion_client=completion_client)

    result = await service.detect_columns(
        headers=["question", "answer", "domain"],
        sample_rows=[{"question": "Q", "answer": "A", "domain": "Security"}],
        deterministic_result=CsvColumnMappingResult(
            question_col="question",
            answer_col="answer",
            domain_col="domain",
            unresolved_targets=[],
            ambiguous_targets=[],
        ),
    )

    assert result.detected_columns == DetectedCsvColumns(
        question_col="question",
        answer_col="answer",
        domain_col="domain",
    )
    assert result.used_llm is False
    assert completion_client.calls == []


async def test_detect_columns_calls_llm_with_headers_and_first_five_rows() -> None:
    completion_client = FakeCompletionClient(
        '{"question_col":"prompt_text","answer_col":"response_text","domain_col":"category"}'
    )
    service = CsvColumnDetectionService(completion_client=completion_client)

    result = await service.detect_columns(
        headers=["prompt_text", "response_text", "category"],
        sample_rows=[
            {"prompt_text": "Q1", "response_text": "A1", "category": "Security"},
            {"prompt_text": "Q2", "response_text": "A2", "category": "AI"},
        ],
        deterministic_result=CsvColumnMappingResult(
            question_col=None,
            answer_col=None,
            domain_col=None,
            unresolved_targets=["question", "answer", "domain"],
            ambiguous_targets=[],
        ),
    )

    assert result.detected_columns == DetectedCsvColumns(
        question_col="prompt_text",
        answer_col="response_text",
        domain_col="category",
    )
    assert result.used_llm is True
    assert "prompt_text" in completion_client.calls[0][1]
    assert "Q1" in completion_client.calls[0][1]


async def test_detect_columns_rejects_invalid_llm_json_output() -> None:
    service = CsvColumnDetectionService(completion_client=FakeCompletionClient("not-json"))

    result = await service.detect_columns(
        headers=["a", "b", "c"],
        sample_rows=[{"a": "1", "b": "2", "c": "3"}],
        deterministic_result=CsvColumnMappingResult(
            question_col=None,
            answer_col=None,
            domain_col=None,
            unresolved_targets=["question", "answer", "domain"],
            ambiguous_targets=[],
        ),
    )

    assert result.detected_columns is None
    assert result.error_code == "column_mapping_failed"


async def test_detect_columns_rejects_llm_columns_not_present_in_csv() -> None:
    service = CsvColumnDetectionService(
        completion_client=FakeCompletionClient(
            '{"question_col":"foo","answer_col":"bar","domain_col":"baz"}'
        )
    )

    result = await service.detect_columns(
        headers=["question", "answer", "domain"],
        sample_rows=[{"question": "Q", "answer": "A", "domain": "Security"}],
        deterministic_result=CsvColumnMappingResult(
            question_col=None,
            answer_col=None,
            domain_col=None,
            unresolved_targets=["question", "answer", "domain"],
            ambiguous_targets=[],
        ),
    )

    assert result.detected_columns is None
    assert result.error_code == "column_mapping_failed"


async def test_detect_columns_converts_llm_exception_to_file_level_failure() -> None:
    service = CsvColumnDetectionService(
        completion_client=FakeCompletionClient("", should_raise=True)
    )

    result = await service.detect_columns(
        headers=["question", "answer", "domain"],
        sample_rows=[{"question": "Q", "answer": "A", "domain": "Security"}],
        deterministic_result=CsvColumnMappingResult(
            question_col=None,
            answer_col=None,
            domain_col=None,
            unresolved_targets=["question", "answer", "domain"],
            ambiguous_targets=[],
        ),
    )

    assert result.detected_columns is None
    assert result.error_code == "column_mapping_failed"
    assert "llm unavailable" in (result.error_message or "")
