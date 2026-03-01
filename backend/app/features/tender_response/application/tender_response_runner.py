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
        workflow_config = self._build_workflow_config(
            session_id=options.session_id,
            request_id=request_id,
        )
        debug_log(
            f"request={request_id} workflow config thread_id="
            f"{workflow_config['configurable']['thread_id']}"
        )
        session_completed_results = await self._load_session_completed_results(
            workflow=workflow,
            config=workflow_config,
        )
        debug_log(
            f"request={request_id} loaded session memory "
            f"completed_results={len(session_completed_results)}"
        )
        result = await workflow.ainvoke(
            self._build_initial_state(
                request_id=request_id,
                filename=filename,
                options=options,
                parsed_questions=parsed_csv.questions,
                session_completed_results=session_completed_results,
            ),
            config=workflow_config,
        )
        total_duration_ms = (perf_counter() - started_at) * 1000
        debug_log(
            f"request={request_id} workflow completed "
            f"questions={result['summary'].total_questions_processed} "
            f"duration_ms={total_duration_ms:.2f}"
        )

        return TenderResponseWorkflowResponse(
            request_id=request_id,
            session_id=options.session_id or request_id,
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
        session_completed_results: list,
    ) -> dict:
        """Seed every workflow field explicitly so graph state starts from a stable shape."""

        return {
            "request_id": request_id,
            "session_id": options.session_id,
            "source_file_name": filename,
            "alignment_threshold": options.alignment_threshold,
            "questions": parsed_questions,
            "question_results": [],
            "session_completed_results": session_completed_results,
            "conflict_findings": [],
            "conflict_review_errors": [],
            "run_errors": [],
            "summary": None,
            "current_question": None,
            "current_conflict_job": None,
        }

    def _build_workflow_config(
        self,
        *,
        session_id: str | None,
        request_id: str,
    ) -> dict:
        thread_id = session_id or request_id
        return {"configurable": {"thread_id": thread_id}}

    async def _load_session_completed_results(
        self,
        *,
        workflow,
        config: dict,
    ) -> list:
        if not hasattr(workflow, "aget_state"):
            return []

        snapshot = await workflow.aget_state(config)
        values = getattr(snapshot, "values", {}) or {}
        session_completed_results = values.get("session_completed_results", [])
        return list(session_completed_results)
