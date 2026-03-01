from app.features.tender_response.domain.models import TenderQuestion


def build_normalizer():
    from app.features.tender_response.infrastructure.parsers.tender_tabular_normalizer import (
        TenderTabularNormalizer,
    )

    return TenderTabularNormalizer()


def assert_question(
    question: TenderQuestion,
    *,
    question_id: str,
    original_question: str,
    declared_domain: str | None,
    source_file_name: str,
    source_row_index: int,
) -> None:
    assert question.question_id == question_id
    assert question.original_question == original_question
    assert question.declared_domain == declared_domain
    assert question.source_file_name == source_file_name
    assert question.source_row_index == source_row_index


def test_tender_tabular_normalizer_extracts_questions_from_tabular_rows() -> None:
    normalizer = build_normalizer()

    result = normalizer.normalize_rows(
        headers=["question_id", "domain", "question"],
        rows=[
            {
                "question_id": "q-001",
                "domain": "Security",
                "question": "Do you support TLS 1.2 or higher?",
            },
            {
                "question_id": "",
                "domain": "",
                "question": "Do you support SAML SSO?",
            },
        ],
        source_file_name="tender.xlsx",
    )

    assert len(result.questions) == 2
    assert_question(
        result.questions[0],
        question_id="q-001",
        original_question="Do you support TLS 1.2 or higher?",
        declared_domain="Security",
        source_file_name="tender.xlsx",
        source_row_index=0,
    )
    assert_question(
        result.questions[1],
        question_id="row-2",
        original_question="Do you support SAML SSO?",
        declared_domain=None,
        source_file_name="tender.xlsx",
        source_row_index=1,
    )


def test_tender_tabular_normalizer_uses_shared_header_aliases_and_stable_row_indices() -> None:
    normalizer = build_normalizer()

    result = normalizer.normalize_rows(
        headers=["ID", "Category", "Question Text"],
        rows=[
            {
                "ID": "q-001",
                "Category": "Security",
                "Question Text": "Do you support TLS 1.2 or higher?",
            },
            {
                "ID": "q-ignored",
                "Category": "Security",
                "Question Text": "   ",
            },
            {
                "ID": "",
                "Category": "Identity",
                "Question Text": "Do you support SCIM provisioning?",
            },
        ],
        source_file_name="tender.xlsx",
    )

    assert len(result.questions) == 2
    assert [question.question_id for question in result.questions] == ["q-001", "row-3"]
    assert [question.source_row_index for question in result.questions] == [0, 2]
    assert result.questions[1].declared_domain == "Identity"


def test_tender_tabular_normalizer_rejects_rows_without_question_column() -> None:
    normalizer = build_normalizer()

    try:
        normalizer.normalize_rows(
            headers=["domain", "client_priority"],
            rows=[{"domain": "Security", "client_priority": "High"}],
            source_file_name="tender.xlsx",
        )
    except ValueError as exc:
        assert "question column" in str(exc).lower()
    else:
        raise AssertionError("Expected parser to reject tabular input without a question column")
