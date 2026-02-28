import csv
from io import StringIO

from app.features.tender_response.domain.models import TenderCsvParseResult, TenderQuestion
from app.features.tender_response.domain.question_extraction import (
    DOMAIN_COLUMN_CANDIDATES,
    QUESTION_COLUMN_CANDIDATES,
    QUESTION_ID_COLUMN_CANDIDATES,
    find_first_matching_column,
)


class TenderCsvParser:
    def parse_text(self, raw_text: str, *, source_file_name: str) -> TenderCsvParseResult:
        reader = csv.DictReader(StringIO(raw_text))
        headers = reader.fieldnames or []

        question_column = find_first_matching_column(headers, QUESTION_COLUMN_CANDIDATES)
        if question_column is None:
            raise ValueError("CSV must include a question column.")

        question_id_column = find_first_matching_column(headers, QUESTION_ID_COLUMN_CANDIDATES)
        domain_column = find_first_matching_column(headers, DOMAIN_COLUMN_CANDIDATES)

        questions: list[TenderQuestion] = []
        for row_index, row in enumerate(reader):
            question_text = (row.get(question_column) or "").strip()
            if not question_text:
                continue

            question_id = (row.get(question_id_column) or "").strip() if question_id_column else ""
            questions.append(
                TenderQuestion(
                    question_id=question_id or f"row-{row_index + 1}",
                    original_question=question_text,
                    declared_domain=(row.get(domain_column) or "").strip() or None
                    if domain_column
                    else None,
                    source_file_name=source_file_name,
                    source_row_index=row_index,
                    raw_row={key: value or "" for key, value in row.items()},
                )
            )

        return TenderCsvParseResult(source_file_name=source_file_name, questions=questions)
