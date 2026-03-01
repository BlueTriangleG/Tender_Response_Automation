"""HTTP routes for tender-response generation."""

from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from app.core.config import settings
from app.features.tender_response.api.dependencies import get_tender_response_runner
from app.features.tender_response.application.tender_response_runner import (
    TenderResponseRunner,
)
from app.features.tender_response.schemas.requests import TenderResponseRequestOptions
from app.features.tender_response.schemas.responses import TenderResponseWorkflowResponse

router = APIRouter(prefix=settings.api_prefix)
TenderResponseRunnerDep = Annotated[
    TenderResponseRunner,
    Depends(get_tender_response_runner),
]


@router.post("/tender/respond", response_model=TenderResponseWorkflowResponse)
async def tender_respond(
    file: Annotated[UploadFile, File()],
    runner: TenderResponseRunnerDep,
    session_id: Annotated[str | None, Form(alias="sessionId")] = None,
    alignment_threshold: Annotated[float, Form(alias="alignmentThreshold")] = 0.5,
) -> TenderResponseWorkflowResponse:
    """Generate tender answers for the uploaded CSV and return workflow results."""

    try:
        options = TenderResponseRequestOptions(
            session_id=session_id,
            alignment_threshold=alignment_threshold,
        )
        return await runner.process_upload(file, options, workflow_name="parallel")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
