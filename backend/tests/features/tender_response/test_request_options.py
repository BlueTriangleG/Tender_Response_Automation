from app.features.tender_response.schemas.requests import TenderResponseRequestOptions


def test_tender_response_request_options_defaults_alignment_threshold_to_point_five() -> None:
    options = TenderResponseRequestOptions()

    assert options.alignment_threshold == 0.5
