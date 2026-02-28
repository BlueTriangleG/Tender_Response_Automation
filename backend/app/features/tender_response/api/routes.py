from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from app.core.config import settings
from app.features.tender_response.api.dependencies import get_process_tender_csv_use_case
from app.features.tender_response.application.process_tender_csv_use_case import (
    ProcessTenderCsvUseCase,
)
from app.features.tender_response.schemas.requests import TenderResponseRequestOptions
from app.features.tender_response.schemas.responses import TenderResponseWorkflowResponse

router = APIRouter(prefix=settings.api_prefix)


@router.post("/tender/respond", response_model=TenderResponseWorkflowResponse)
async def tender_respond(
    file: Annotated[UploadFile, File()],
    session_id: Annotated[str | None, Form(alias="sessionId")] = None,
    alignment_threshold: Annotated[float, Form(alias="alignmentThreshold")] = 0.82,
    use_case: Annotated[ProcessTenderCsvUseCase, Depends(get_process_tender_csv_use_case)] = None,
) -> TenderResponseWorkflowResponse:
    try:
        option_kwargs = {"alignment_threshold": alignment_threshold}
        if session_id:
            option_kwargs["session_id"] = session_id
        options = TenderResponseRequestOptions(**option_kwargs)
        return await use_case.process_upload(file, options)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
