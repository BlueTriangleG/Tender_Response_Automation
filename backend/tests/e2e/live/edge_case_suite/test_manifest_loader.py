from tests.e2e.live.edge_case_suite.manifest_loader import load_manifest


def test_edge_case_manifest_includes_xlsx_tender_input() -> None:
    manifest = load_manifest()

    xlsx_cases = [case for case in manifest.tender_inputs if case.file.suffix == ".xlsx"]

    assert xlsx_cases
    assert all(case.file.exists() for case in xlsx_cases)
