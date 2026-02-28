from fastapi.testclient import TestClient

from app.main import app


def test_history_ingest_route_accepts_single_upload_tender_file() -> None:
    client = TestClient(app)

    response = client.post(
        "/api/ingest/history",
        files={
            "file": (
                "tender.csv",
                b"question,domain\nSubmission readiness,Transport\n",
                "text/csv",
            )
        },
        data={
            "outputFormat": "excel",
            "similarityThreshold": "0.81",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["total_file_count"] == 1
    assert payload["processed_file_count"] == 1
    assert payload["failed_file_count"] == 0
    assert payload["request_options"] == {
        "output_format": "excel",
        "similarity_threshold": 0.81,
    }
    assert payload["files"][0]["payload"]["file_name"] == "tender.csv"


def test_history_ingest_route_accepts_batch_files_under_files_field() -> None:
    client = TestClient(app)

    response = client.post(
        "/api/ingest/history",
        files=[
            (
                "files",
                ("history.json", b'{"hello":"world"}', "application/json"),
            ),
            (
                "files",
                ("notes.md", b"# Notes", "text/markdown"),
            ),
        ],
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["total_file_count"] == 2
    assert payload["processed_file_count"] == 2
    assert payload["failed_file_count"] == 0
    assert [item["status"] for item in payload["files"]] == [
        "processed",
        "processed",
    ]


def test_history_ingest_route_returns_422_without_any_files() -> None:
    client = TestClient(app)

    response = client.post("/api/ingest/history")

    assert response.status_code == 422
