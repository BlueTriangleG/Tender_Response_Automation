"""Heuristic confidence classification for tender-answer alignment."""

from app.features.tender_response.domain.models import HistoricalAlignmentResult


class ConfidenceService:
    """Map alignment and safety signals onto a coarse confidence level."""

    def classify(
        self,
        *,
        alignment: HistoricalAlignmentResult,
        high_risk: bool,
        inconsistent_response: bool,
    ) -> str:
        """Lower confidence whenever risk signals exist, otherwise use match strength."""

        if high_risk or inconsistent_response:
            return "low"
        if alignment.matched and (alignment.alignment_score or 0.0) >= 0.9:
            return "high"
        if alignment.matched:
            return "medium"
        return "low"
