from app.services.qa_embedding_service import QaEmbeddingService


class FakeEmbeddingItem:
    def __init__(self, embedding: list[float]) -> None:
        self.embedding = embedding


class FakeEmbeddingResponse:
    def __init__(self, embeddings: list[list[float]]) -> None:
        self.data = [FakeEmbeddingItem(embedding) for embedding in embeddings]


class FakeEmbeddingsClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, list[str]]] = []
        self.embeddings = self

    async def create(self, *, model: str, input: list[str]) -> FakeEmbeddingResponse:
        self.calls.append((model, input))
        return FakeEmbeddingResponse([[0.1, 0.2, 0.3] for _ in input])


async def test_embed_texts_uses_configured_embedding_model() -> None:
    client = FakeEmbeddingsClient()
    service = QaEmbeddingService(client=client, model="text-embedding-3-small")

    result = await service.embed_texts(["Question: Q\nAnswer: A\nDomain: Security"])

    assert result == [[0.1, 0.2, 0.3]]
    assert client.calls == [
        ("text-embedding-3-small", ["Question: Q\nAnswer: A\nDomain: Security"])
    ]
