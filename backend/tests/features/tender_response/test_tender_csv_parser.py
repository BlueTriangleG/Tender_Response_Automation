from app.features.tender_response.infrastructure.parsers.tender_csv_parser import (
    TenderCsvParser,
)


def test_tender_csv_parser_extracts_questions_from_csv_rows() -> None:
    parser = TenderCsvParser()

    result = parser.parse_text(
        "question_id,domain,question\n"
        'q-001,Security,"Do you support TLS 1.2 or higher?"\n'
        'q-002,Compliance,"Are customer backups encrypted at rest?"\n',
        source_file_name="tender.csv",
    )

    assert len(result.questions) == 2
    assert result.questions[0].question_id == "q-001"
    assert result.questions[0].original_question == "Do you support TLS 1.2 or higher?"
    assert result.questions[1].declared_domain == "Compliance"


def test_tender_csv_parser_supports_missing_optional_columns() -> None:
    parser = TenderCsvParser()

    result = parser.parse_text(
        "question\n"
        '"Do you support SAML SSO?"\n',
        source_file_name="tender.csv",
    )

    assert len(result.questions) == 1
    assert result.questions[0].question_id == "row-1"
    assert result.questions[0].declared_domain is None


def test_tender_csv_parser_does_not_apply_a_hard_coded_question_limit() -> None:
    parser = TenderCsvParser()
    rows = ["question"] + [f'"Question {index}?"' for index in range(1, 26)]

    result = parser.parse_text("\n".join(rows), source_file_name="tender.csv")

    assert len(result.questions) == 25


def test_tender_csv_parser_rejects_csv_without_question_column() -> None:
    parser = TenderCsvParser()

    try:
        parser.parse_text(
            "domain,client_priority\nSecurity,High\n",
            source_file_name="tender.csv",
        )
    except ValueError as exc:
        assert "question column" in str(exc).lower()
    else:
        raise AssertionError("Expected parser to reject CSV without a question column")
