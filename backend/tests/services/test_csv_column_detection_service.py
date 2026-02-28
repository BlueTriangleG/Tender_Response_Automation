from app.file_processing.csv_column_mapping import CsvColumnMappingResult
from app.schemas.history_ingest import DetectedCsvColumns
from app.services.csv_column_detection_service import CsvColumnDetectionService


class FakeAgent:
    def __init__(self, response: str, should_raise: bool = False) -> None:
        self.response = response
        self.should_raise = should_raise
        self.messages: list[str] = []

    async def chat(self, message: str) -> str:
        self.messages.append(message)
        if self.should_raise:
            raise RuntimeError("llm unavailable")
        return self.response


class FakeAgentManager:
    def __init__(self, agent: FakeAgent) -> None:
        self.agent = agent
        self.calls: list[tuple[str, str]] = []

    def get_agent(self, session_id: str, workflow_name: str = "react_agent") -> FakeAgent:
        self.calls.append((session_id, workflow_name))
        return self.agent


async def test_detect_columns_skips_llm_when_mapping_is_complete() -> None:
    manager = FakeAgentManager(FakeAgent('{"question_col":"q","answer_col":"a","domain_col":"d"}'))
    service = CsvColumnDetectionService(agent_manager_instance=manager)

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
    assert manager.calls == []


async def test_detect_columns_calls_llm_with_headers_and_first_five_rows() -> None:
    agent = FakeAgent('{"question_col":"prompt_text","answer_col":"response_text","domain_col":"category"}')
    manager = FakeAgentManager(agent)
    service = CsvColumnDetectionService(agent_manager_instance=manager)

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
    assert manager.calls[0][1] == "csv_column_detection_agent"
    assert "prompt_text" in agent.messages[0]
    assert "Q1" in agent.messages[0]


async def test_detect_columns_rejects_invalid_llm_json_output() -> None:
    service = CsvColumnDetectionService(
        agent_manager_instance=FakeAgentManager(FakeAgent("not-json"))
    )

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
        agent_manager_instance=FakeAgentManager(
            FakeAgent('{"question_col":"foo","answer_col":"bar","domain_col":"baz"}')
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
        agent_manager_instance=FakeAgentManager(FakeAgent("", should_raise=True))
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
