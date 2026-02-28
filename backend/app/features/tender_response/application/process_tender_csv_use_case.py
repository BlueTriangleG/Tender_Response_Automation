"""Application service for tender CSV processing and response generation."""

from pathlib import Path
from uuid import uuid4

from langgraph.graph.state import CompiledStateGraph
from starlette.datastructures import UploadFile

from app.features.tender_response.infrastructure.parsers.tender_csv_parser import (
    TenderCsvParser,
)
from app.features.tender_response.infrastructure.workflows.tender_response_graph import (
    create_tender_response_graph,
)
from app.features.tender_response.schemas.requests import TenderResponseRequestOptions
from app.features.tender_response.schemas.responses import TenderResponseWorkflowResponse


class ProcessTenderCsvUseCase:
    """Validate the upload, parse questions, and execute the tender workflow."""

    def __init__(
        self,
        parser: TenderCsvParser | None = None,
        workflow: CompiledStateGraph | None = None,
    ) -> None:
        self._parser = parser or TenderCsvParser()
        self._workflow = workflow or create_tender_response_graph()

    async def process_upload(
        self,
        upload_file: UploadFile,
        options: TenderResponseRequestOptions,
    ) -> TenderResponseWorkflowResponse:
        """Run the full tender-response workflow for one uploaded CSV file."""

        filename = upload_file.filename or "unknown"
        request_id = str(uuid4())
        if Path(filename).suffix.lower() != ".csv":
            raise ValueError("Only CSV files are supported for tender response generation.")

        # Decode once at the use-case boundary so the parser and workflow can assume text input.
        raw_bytes = await upload_file.read()
        try:
            raw_text = raw_bytes.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ValueError(f"Failed to decode CSV as UTF-8: {filename}") from exc

        parsed_csv = self._parser.parse_text(raw_text, source_file_name=filename)
        # Seed every workflow field explicitly so the compiled LangGraph state starts
        # from a complete, predictable shape.
        result = await self._workflow.ainvoke(
            {
                "request_id": request_id,
                "session_id": options.session_id,
                "source_file_name": filename,
                "alignment_threshold": options.alignment_threshold,
                "questions": parsed_csv.questions,
                "question_results": [],
                "run_errors": [],
                "summary": None,
                "current_question": None,
                "current_alignment": None,
                "current_assessment": None,
                "current_review": None,
                "current_grounded_result": None,
                "current_answer": None,
                "current_result": None,
            },
            config={"configurable": {"thread_id": request_id}},
        )

        # The API response is a projection of workflow state, not a separate source of truth.
        return TenderResponseWorkflowResponse(
            request_id=request_id,
            session_id=options.session_id,
            source_file_name=filename,
            total_questions_processed=result["summary"].total_questions_processed,
            questions=result["question_results"],
            summary=result["summary"],
        )
