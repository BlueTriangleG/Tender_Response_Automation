from lancedb.db import DBConnection

from app.core.config import settings
from app.db.lancedb_client import ensure_lancedb_ready
from app.features.tender_response.domain.models import (
    HistoricalAlignmentResult,
    TenderQuestion,
)
from app.integrations.openai.embeddings_client import OpenAIEmbeddingsClient


class QaAlignmentRepository:
    def __init__(
        self,
        connection: DBConnection | None = None,
        embeddings_client: OpenAIEmbeddingsClient | None = None,
    ) -> None:
        self._connection = connection or ensure_lancedb_ready()
        self._embeddings_client = embeddings_client or OpenAIEmbeddingsClient()
        self._table_name = settings.lancedb_qa_table_name

    async def find_best_match(
        self,
        question: TenderQuestion,
        *,
        threshold: float,
    ) -> HistoricalAlignmentResult:
        table = self._connection.open_table(self._table_name)
        rows = table.to_arrow().to_pylist()
        if not rows:
            return HistoricalAlignmentResult(
                matched=False,
                record_id=None,
                question=None,
                answer=None,
                domain=None,
                alignment_score=None,
            )

        [query_vector] = await self._embeddings_client.embed_texts([question.original_question])
        matches = table.search(query_vector).limit(1).to_list()
        if not matches:
            return HistoricalAlignmentResult(
                matched=False,
                record_id=None,
                question=None,
                answer=None,
                domain=None,
                alignment_score=None,
            )

        best_match = matches[0]
        distance = float(best_match.get("_distance", 1.0))
        alignment_score = 1.0 / (1.0 + distance)
        if alignment_score < threshold:
            return HistoricalAlignmentResult(
                matched=False,
                record_id=None,
                question=None,
                answer=None,
                domain=None,
                alignment_score=alignment_score,
            )

        return HistoricalAlignmentResult(
            matched=True,
            record_id=best_match.get("id"),
            question=best_match.get("question"),
            answer=best_match.get("answer"),
            domain=best_match.get("domain"),
            alignment_score=alignment_score,
        )
