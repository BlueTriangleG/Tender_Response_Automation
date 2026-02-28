from typing import Annotated, Literal

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from app.core.config import settings
from app.schemas.history_ingest import HistoryIngestRequestOptions, HistoryIngestResponse
from app.services.history_ingest_service import HistoryIngestService

router = APIRouter(prefix=settings.api_prefix)


@router.post("/ingest/history", response_model=HistoryIngestResponse)
async def ingest_history(
    files: Annotated[list[UploadFile] | None, File()] = None,
    file: Annotated[UploadFile | None, File()] = None,
    output_format: Annotated[Literal["json", "excel"], Form(alias="outputFormat")] = "json",
    similarity_threshold: Annotated[float, Form(alias="similarityThreshold")] = 0.72,
) -> HistoryIngestResponse:
    uploads = list(files or [])

    if file is not None:
        uploads.insert(0, file)

    if not uploads:
        raise HTTPException(status_code=422, detail="At least one uploaded file is required.")

    service = HistoryIngestService()
    request_options = HistoryIngestRequestOptions(
        output_format=output_format,
        similarity_threshold=similarity_threshold,
    )
    return await service.process_files(uploads, request_options=request_options)
