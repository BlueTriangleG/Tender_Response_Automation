from app.integrations.openai.embeddings_client import OpenAIEmbeddingsClient


class FakeEmbeddingItem:
    def __init__(self, embedding: list[float]) -> None:
        self.embedding = embedding


class FakeEmbeddingResponse:
    def __init__(self, embeddings: list[list[float]]) -> None:
        self.data = [FakeEmbeddingItem(embedding) for embedding in embeddings]


class FakeAsyncOpenAI:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []
        self.embeddings = self

    async def create(self, *, model: str, input: list[str]) -> FakeEmbeddingResponse:
        self.calls.append({"model": model, "input": input})
        return FakeEmbeddingResponse([[0.1, 0.2, 0.3] for _ in input])


async def test_embeddings_client_calls_openai_sdk() -> None:
    client = FakeAsyncOpenAI()
    adapter = OpenAIEmbeddingsClient(client=client, model="text-embedding-3-small")

    result = await adapter.embed_texts(["Question: Q\nAnswer: A\nDomain: Security"])

    assert result == [[0.1, 0.2, 0.3]]
    assert client.calls == [
        {
            "model": "text-embedding-3-small",
            "input": ["Question: Q\nAnswer: A\nDomain: Security"],
        }
    ]
