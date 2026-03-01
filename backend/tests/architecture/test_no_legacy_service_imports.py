from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
APP_ROOT = PROJECT_ROOT / "app"
TEST_ROOT = PROJECT_ROOT / "tests"


def _python_files(root: Path) -> list[Path]:
    return [path for path in root.rglob("*.py") if "__pycache__" not in path.parts]


def test_no_backend_code_imports_legacy_app_services() -> None:
    offenders: list[str] = []

    for root in [APP_ROOT, TEST_ROOT]:
        for path in _python_files(root):
            if path.name == "test_no_legacy_service_imports.py":
                continue

            content = path.read_text(encoding="utf-8")
            if "app.services." in content or "from app.services import" in content:
                offenders.append(str(path.relative_to(PROJECT_ROOT)))

    assert offenders == []
