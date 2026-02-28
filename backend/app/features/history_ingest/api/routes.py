from typing import Annotated, Literal

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from app.core.config import settings
from app.features.history_ingest.api.dependencies import get_history_ingest_use_case
from app.features.history_ingest.application.ingest_history_use_case import (
    IngestHistoryUseCase,
)
from app.features.history_ingest.schemas.requests import HistoryIngestRequestOptions
from app.features.history_ingest.schemas.responses import HistoryIngestResponse

router = APIRouter(prefix=settings.api_prefix)


@router.post("/ingest/history", response_model=HistoryIngestResponse)
async def ingest_history(
    files: Annotated[list[UploadFile] | None, File()] = None,
    file: Annotated[UploadFile | None, File()] = None,
    output_format: Annotated[Literal["json", "excel"], Form(alias="outputFormat")] = "json",
    similarity_threshold: Annotated[float, Form(alias="similarityThreshold")] = 0.72,
    use_case: Annotated[IngestHistoryUseCase, Depends(get_history_ingest_use_case)] = None,
) -> HistoryIngestResponse:
    uploads = list(files or [])

    if file is not None:
        uploads.insert(0, file)

    if not uploads:
        raise HTTPException(status_code=422, detail="At least one uploaded file is required.")

    request_options = HistoryIngestRequestOptions(
        output_format=output_format,
        similarity_threshold=similarity_threshold,
    )
    return await use_case.process_files(uploads, request_options=request_options)
