from importlib import import_module


def test_tender_response_feature_modules_are_importable() -> None:
    modules = [
        "app.features.tender_response.api.routes",
        "app.features.tender_response.api.dependencies",
        "app.features.tender_response.application.process_tender_csv_use_case",
        "app.features.tender_response.domain.models",
        "app.features.tender_response.domain.question_extraction",
        "app.features.tender_response.domain.risk_rules",
        "app.features.tender_response.infrastructure.parsers.tender_csv_parser",
        "app.features.tender_response.infrastructure.repositories.qa_alignment_repository",
        "app.features.tender_response.infrastructure.services.answer_generation_service",
        "app.features.tender_response.infrastructure.services.confidence_service",
        "app.features.tender_response.infrastructure.services.domain_tagging_service",
        "app.features.tender_response.infrastructure.workflows.tender_response_graph",
        "app.features.tender_response.schemas.requests",
        "app.features.tender_response.schemas.responses",
    ]

    for module_name in modules:
        imported = import_module(module_name)
        assert imported is not None
