"""Historical QA retrieval adapter used by the tender-response workflow."""

from lancedb.db import DBConnection

from app.core.config import settings
from app.db.lancedb_client import ensure_lancedb_ready
from app.features.tender_response.domain.models import (
    HistoricalAlignmentResult,
    HistoricalReference,
    TenderQuestion,
)
from app.integrations.openai.embeddings_client import OpenAIEmbeddingsClient


class QaAlignmentRepository:
    """Find the best historical QA records to ground a tender answer."""

    def __init__(
        self,
        connection: DBConnection | None = None,
        embeddings_client: OpenAIEmbeddingsClient | None = None,
    ) -> None:
        self._connection = connection if connection is not None else ensure_lancedb_ready()
        self._embeddings_client = embeddings_client or OpenAIEmbeddingsClient()
        self._table_name = settings.lancedb_qa_table_name

    async def find_best_matches(
        self,
        question: TenderQuestion,
        *,
        threshold: float,
        limit: int = 3,
    ) -> list[HistoricalReference]:
        """Return top QA candidates for downstream thresholding and conflict checks."""

        table = self._connection.open_table(self._table_name)
        rows = table.to_arrow().to_pylist()
        if not rows:
            return []

        [query_vector] = await self._embeddings_client.embed_texts([question.original_question])
        matches = table.search(query_vector).limit(limit).to_list()
        if not matches:
            return []

        candidate_references = [
            HistoricalReference(
                record_id=str(match["id"]),
                reference_type="qa",
                question=str(match["question"]),
                answer=str(match["answer"]),
                domain=match.get("domain"),
                source_doc=match.get("source_doc"),
                alignment_score=1.0 / (1.0 + float(match.get("_distance", 1.0))),
            )
            for match in matches
        ]
        return candidate_references

    async def find_best_match(
        self,
        question: TenderQuestion,
        *,
        threshold: float,
    ) -> HistoricalAlignmentResult:
        """Search LanceDB and keep only references whose score clears the threshold."""

        references = await self.find_best_matches(
            question,
            threshold=threshold,
            limit=3,
        )
        if not references:
            return HistoricalAlignmentResult(
                matched=False,
                record_id=None,
                question=None,
                answer=None,
                domain=None,
                source_doc=None,
                alignment_score=None,
                references=[],
            )

        best_reference = references[0]
        if best_reference.alignment_score < threshold:
            return HistoricalAlignmentResult(
                matched=False,
                record_id=None,
                question=None,
                answer=None,
                domain=None,
                source_doc=None,
                alignment_score=best_reference.alignment_score,
                references=references,
            )

        selected_reference = best_reference
        return HistoricalAlignmentResult(
            matched=True,
            record_id=selected_reference.record_id,
            question=selected_reference.question,
            answer=selected_reference.answer,
            domain=selected_reference.domain,
            source_doc=selected_reference.source_doc,
            alignment_score=selected_reference.alignment_score,
            references=references,
        )
