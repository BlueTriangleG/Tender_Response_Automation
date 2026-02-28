from app.features.tender_response.domain.models import HistoricalAlignmentResult


class ConfidenceService:
    def classify(
        self,
        *,
        alignment: HistoricalAlignmentResult,
        high_risk: bool,
        inconsistent_response: bool,
    ) -> str:
        if high_risk or inconsistent_response:
            return "low"
        if alignment.matched and (alignment.alignment_score or 0.0) >= 0.9:
            return "high"
        if alignment.matched:
            return "medium"
        return "low"
