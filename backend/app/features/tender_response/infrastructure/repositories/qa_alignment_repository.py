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
        self._connection = connection or ensure_lancedb_ready()
        self._embeddings_client = embeddings_client or OpenAIEmbeddingsClient()
        self._table_name = settings.lancedb_qa_table_name

    async def find_best_match(
        self,
        question: TenderQuestion,
        *,
        threshold: float,
    ) -> HistoricalAlignmentResult:
        """Search LanceDB and keep only references whose score clears the threshold."""

        table = self._connection.open_table(self._table_name)
        rows = table.to_arrow().to_pylist()
        # LanceDB search fails conceptually when the table is empty, so short-circuit
        # early and return a structured "no match" result.
        if not rows:
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

        # Embed the incoming tender question into the same vector space as the
        # historical QA records before running nearest-neighbour search.
        [query_vector] = await self._embeddings_client.embed_texts([question.original_question])
        matches = table.search(query_vector).limit(3).to_list()
        if not matches:
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

        # Convert LanceDB distance into a bounded score so the rest of the workflow
        # can apply a consistent threshold regardless of backend-specific distance semantics.
        candidate_references = [
            HistoricalReference(
                record_id=str(match["id"]),
                question=str(match["question"]),
                answer=str(match["answer"]),
                domain=match.get("domain"),
                source_doc=match.get("source_doc"),
                alignment_score=1.0 / (1.0 + float(match.get("_distance", 1.0))),
            )
            for match in matches
        ]
        best_reference = candidate_references[0]
        qualified_references = [
            reference
            for reference in candidate_references
            if reference.alignment_score >= threshold
        ]

        # Preserve candidate_references even on a miss so downstream services can still
        # inspect near-matches when deciding why grounding failed.
        if not qualified_references:
            return HistoricalAlignmentResult(
                matched=False,
                record_id=None,
                question=None,
                answer=None,
                domain=None,
                source_doc=None,
                alignment_score=best_reference.alignment_score,
                references=candidate_references,
            )

        selected_reference = qualified_references[0]
        return HistoricalAlignmentResult(
            matched=True,
            record_id=selected_reference.record_id,
            question=selected_reference.question,
            answer=selected_reference.answer,
            domain=selected_reference.domain,
            source_doc=selected_reference.source_doc,
            alignment_score=selected_reference.alignment_score,
            references=qualified_references,
        )
