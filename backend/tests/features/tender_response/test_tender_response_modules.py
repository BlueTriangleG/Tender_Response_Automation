from importlib import import_module


def test_tender_response_feature_modules_are_importable() -> None:
    modules = [
        "app.features.tender_response.api.routes",
        "app.features.tender_response.api.dependencies",
        "app.features.tender_response.application.tender_response_runner",
        "app.features.tender_response.domain.conflict_rules",
        "app.features.tender_response.domain.models",
        "app.features.tender_response.domain.question_extraction",
        "app.features.tender_response.domain.risk_rules",
        "app.features.tender_response.infrastructure.parsers.tender_csv_parser",
        "app.features.tender_response.infrastructure.prompting.answer_generation",
        "app.features.tender_response.infrastructure.prompting.reference_assessment",
        "app.features.tender_response.infrastructure.repositories.document_alignment_repository",
        "app.features.tender_response.infrastructure.repositories.qa_alignment_repository",
        "app.features.tender_response.infrastructure.services.answer_generation_service",
        "app.features.tender_response.infrastructure.services.domain_tagging_service",
        "app.features.tender_response.infrastructure.services.historical_evidence_service",
        "app.features.tender_response.infrastructure.services.reference_assessment_service",
        "app.features.tender_response.infrastructure.workflows.registry",
        "app.features.tender_response.infrastructure.workflows.common.builders",
        "app.features.tender_response.infrastructure.workflows.common.debug",
        "app.features.tender_response.infrastructure.workflows.common.state",
        "app.features.tender_response.infrastructure.workflows.parallel.nodes",
        "app.features.tender_response.infrastructure.workflows.parallel.question_graph",
        "app.features.tender_response.infrastructure.workflows.parallel.routing",
        "app.features.tender_response.infrastructure.workflows.parallel.graph",
        "app.features.tender_response.schemas.requests",
        "app.features.tender_response.schemas.responses",
    ]

    for module_name in modules:
        imported = import_module(module_name)
        assert imported is not None
