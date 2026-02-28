from importlib import import_module


def test_agent_chat_feature_modules_are_importable() -> None:
    modules = [
        "app.features.agent_chat.api.routes",
        "app.features.agent_chat.api.dependencies",
        "app.features.agent_chat.application.chat_use_case",
        "app.features.agent_chat.schemas.requests",
        "app.features.agent_chat.schemas.responses",
    ]

    for module_name in modules:
        imported = import_module(module_name)
        assert imported is not None
