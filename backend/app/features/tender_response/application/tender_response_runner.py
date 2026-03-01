"""Thin application runner for tender-response workflow execution."""

from pathlib import Path
from time import perf_counter
from uuid import uuid4

from starlette.datastructures import UploadFile

from app.features.tender_response.infrastructure.parsers.tender_csv_parser import (
    TenderCsvParser,
)
from app.features.tender_response.infrastructure.workflows.common.debug import debug_log
from app.features.tender_response.infrastructure.workflows.registry import (
    TenderWorkflowName,
    TenderWorkflowRegistry,
)
from app.features.tender_response.schemas.requests import TenderResponseRequestOptions
from app.features.tender_response.schemas.responses import TenderResponseWorkflowResponse


class TenderResponseRunner:
    """Validate uploads, parse CSV input, and invoke the selected workflow family."""

    def __init__(
        self,
        parser: TenderCsvParser | None = None,
        workflow_registry: TenderWorkflowRegistry | None = None,
    ) -> None:
        self._parser = parser or TenderCsvParser()
        self._workflow_registry = workflow_registry or TenderWorkflowRegistry()

    async def process_upload(
        self,
        upload_file: UploadFile,
        options: TenderResponseRequestOptions,
        *,
        workflow_name: TenderWorkflowName = "parallel",
    ) -> TenderResponseWorkflowResponse:
        """Run the selected tender-response workflow for one uploaded CSV file."""

        filename = upload_file.filename or "unknown"
        request_id = str(uuid4())
        started_at = perf_counter()
        if Path(filename).suffix.lower() != ".csv":
            raise ValueError("Only CSV files are supported for tender response generation.")

        debug_log(
            f"request={request_id} upload start file={filename} "
            f"alignment_threshold={options.alignment_threshold} workflow={workflow_name}"
        )

        raw_bytes = await upload_file.read()
        try:
            raw_text = raw_bytes.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ValueError(f"Failed to decode CSV as UTF-8: {filename}") from exc

        parsed_csv = self._parser.parse_text(raw_text, source_file_name=filename)
        debug_log(
            f"request={request_id} parsed questions={len(parsed_csv.questions)} file={filename}"
        )
        workflow = self._workflow_registry.get(workflow_name)
        result = await workflow.ainvoke(
            self._build_initial_state(
                request_id=request_id,
                filename=filename,
                options=options,
                parsed_questions=parsed_csv.questions,
            ),
            config={"configurable": {"thread_id": request_id}},
        )
        total_duration_ms = (perf_counter() - started_at) * 1000
        debug_log(
            f"request={request_id} workflow completed "
            f"questions={result['summary'].total_questions_processed} "
            f"duration_ms={total_duration_ms:.2f}"
        )

        return TenderResponseWorkflowResponse(
            request_id=request_id,
            session_id=options.session_id,
            source_file_name=filename,
            total_questions_processed=result["summary"].total_questions_processed,
            questions=result["question_results"],
            summary=result["summary"],
        )

    def _build_initial_state(
        self,
        *,
        request_id: str,
        filename: str,
        options: TenderResponseRequestOptions,
        parsed_questions: list,
    ) -> dict:
        """Seed every workflow field explicitly so graph state starts from a stable shape."""

        return {
            "request_id": request_id,
            "session_id": options.session_id,
            "source_file_name": filename,
            "alignment_threshold": options.alignment_threshold,
            "questions": parsed_questions,
            "question_results": [],
            "run_errors": [],
            "summary": None,
            "current_question": None,
        }
