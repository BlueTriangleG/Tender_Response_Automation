"""Historical document-chunk retrieval adapter used by the tender-response workflow."""

from lancedb.db import DBConnection

from app.core.config import settings
from app.db.lancedb_client import ensure_lancedb_ready
from app.features.tender_response.domain.models import HistoricalReference, TenderQuestion
from app.integrations.openai.embeddings_client import OpenAIEmbeddingsClient


class DocumentAlignmentRepository:
    """Find the best historical document chunks to ground a tender answer."""

    def __init__(
        self,
        connection: DBConnection | None = None,
        embeddings_client: OpenAIEmbeddingsClient | None = None,
    ) -> None:
        self._connection = connection or ensure_lancedb_ready()
        self._embeddings_client = embeddings_client or OpenAIEmbeddingsClient()
        self._table_name = settings.lancedb_document_table_name

    async def find_best_matches(
        self,
        question: TenderQuestion,
        *,
        threshold: float,
        limit: int = 4,
    ) -> list[HistoricalReference]:
        """Return top document-chunk candidates for downstream thresholding and conflict checks."""

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
                reference_type="document_chunk",
                question="",
                answer="",
                domain=match.get("domain"),
                source_doc=match.get("source_doc"),
                alignment_score=1.0 / (1.0 + float(match.get("_distance", 1.0))),
                excerpt=str(match.get("text") or ""),
                chunk_index=match.get("chunk_index"),
            )
            for match in matches
        ]
        return candidate_references
