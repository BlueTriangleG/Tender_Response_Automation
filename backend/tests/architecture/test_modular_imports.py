from importlib import import_module


def test_modular_backend_packages_are_importable() -> None:
    modules = [
        "app.bootstrap.dependencies",
        "app.bootstrap.routers",
        "app.features.health.api.routes",
        "app.features.health.application.health_check",
        "app.features.health.schemas.responses",
        "app.features.agent_chat.api.routes",
        "app.features.agent_chat.application.chat_use_case",
        "app.features.agent_chat.schemas.requests",
        "app.features.agent_chat.schemas.responses",
        "app.features.history_ingest.api.routes",
        "app.features.history_ingest.application.ingest_history_use_case",
        "app.features.history_ingest.domain.csv_column_mapping",
        "app.features.history_ingest.infrastructure.services.csv_column_detection_service",
        "app.features.tender_response.api.routes",
        "app.features.tender_response.application.process_tender_csv_use_case",
        "app.features.tender_response.infrastructure.services.reference_assessment_service",
        "app.features.tender_response.infrastructure.services.response_review_service",
        "app.features.tender_response.infrastructure.workflows.tender_response_graph",
        "app.features.tender_response.schemas.responses",
        "app.integrations.openai.chat_completions_client",
        "app.integrations.openai.embeddings_client",
    ]

    for module_name in modules:
        imported = import_module(module_name)
        assert imported is not None
