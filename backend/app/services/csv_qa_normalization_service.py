import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime

from app.schemas.history_ingest import DetectedCsvColumns


@dataclass(slots=True)
class NormalizedQaRecord:
    id: str
    domain: str
    question: str
    answer: str
    text: str
    client: str | None
    source_doc: str
    tags: list[str]
    risk_topics: list[str]
    created_at: str
    updated_at: str


@dataclass(slots=True)
class CsvQaNormalizationResult:
    records: list[NormalizedQaRecord]
    failed_row_count: int


class CsvQaNormalizationService:
    def normalize_rows(
        self,
        file_name: str,
        detected_columns: DetectedCsvColumns,
        rows: list[dict[str, str]],
    ) -> CsvQaNormalizationResult:
        timestamp = datetime.now(UTC).isoformat()
        records: list[NormalizedQaRecord] = []
        failed_row_count = 0

        for row_index, row in enumerate(rows):
            question = (row.get(detected_columns.question_col) or "").strip()
            answer = (row.get(detected_columns.answer_col) or "").strip()
            domain = (row.get(detected_columns.domain_col) or "").strip()

            if not question or not answer or not domain:
                failed_row_count += 1
                continue

            text = f"Question: {question}\nAnswer: {answer}\nDomain: {domain}"
            stable_key = f"{file_name}:{row_index}:{question}:{answer}:{domain}"
            record_id = hashlib.sha256(stable_key.encode("utf-8")).hexdigest()

            records.append(
                NormalizedQaRecord(
                    id=record_id,
                    domain=domain,
                    question=question,
                    answer=answer,
                    text=text,
                    client=None,
                    source_doc=file_name,
                    tags=[],
                    risk_topics=[],
                    created_at=timestamp,
                    updated_at=timestamp,
                )
            )

        return CsvQaNormalizationResult(
            records=records,
            failed_row_count=failed_row_count,
        )
