"""Thin application runner for tender-response workflow execution."""

from __future__ import annotations

from pathlib import Path
from time import perf_counter
from typing import TYPE_CHECKING
from uuid import uuid4

from starlette.datastructures import UploadFile

from app.features.tender_response.infrastructure.parsers.base import TenderUploadParser
from app.features.tender_response.infrastructure.parsers.tender_csv_parser import (
    TenderCsvParser,
)
from app.features.tender_response.infrastructure.parsers.tender_excel_parser import (
    TenderExcelParser,
)
from app.features.tender_response.infrastructure.workflows.common.debug import debug_log
from app.features.tender_response.schemas.requests import TenderResponseRequestOptions
from app.features.tender_response.schemas.responses import TenderResponseWorkflowResponse

if TYPE_CHECKING:
    from app.features.tender_response.infrastructure.workflows.registry import (
        TenderWorkflowName,
        TenderWorkflowRegistry,
    )


class TenderResponseRunner:
    """Validate uploads, parse CSV input, and invoke the selected workflow family."""

    def __init__(
        self,
        parser: TenderCsvParser | None = None,
        excel_parser: TenderExcelParser | None = None,
        workflow_registry: TenderWorkflowRegistry | None = None,
    ) -> None:
        self._csv_parser = parser or TenderCsvParser()
        self._excel_parser = excel_parser or TenderExcelParser()
        self._workflow_registry = workflow_registry or self._build_workflow_registry()

    async def process_upload(
        self,
        upload_file: UploadFile,
        options: TenderResponseRequestOptions,
        *,
        workflow_name: TenderWorkflowName = "parallel",
    ) -> TenderResponseWorkflowResponse:
        """Run the selected tender-response workflow for one uploaded tabular file."""

        filename = upload_file.filename or "unknown"
        request_id = str(uuid4())
        started_at = perf_counter()
        parser = self._get_parser_for_filename(filename)

        debug_log(
            f"request={request_id} upload start file={filename} "
            f"alignment_threshold={options.alignment_threshold} workflow={workflow_name}"
        )

        raw_bytes = await upload_file.read()
        parsed_csv = parser.parse_bytes(raw_bytes, source_file_name=filename)
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

    def _build_workflow_registry(self) -> TenderWorkflowRegistry:
        from app.features.tender_response.infrastructure.workflows.registry import (
            TenderWorkflowRegistry,
        )

        return TenderWorkflowRegistry()

    def _get_parser_for_filename(self, filename: str) -> TenderUploadParser:
        suffix = Path(filename).suffix.lower()
        if suffix == ".csv":
            return self._csv_parser
        if suffix == ".xlsx":
            return self._excel_parser
        raise ValueError("Only CSV and XLSX files are supported for tender response generation.")

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
