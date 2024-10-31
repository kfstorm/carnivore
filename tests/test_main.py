from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_clip_url_to_markdown():
    response = client.post(
        "/clip",
        json={
            "url": "https://clickhouse.com/blog/a-new-powerful-json-data-type-for-clickhouse"  # noqa: B950
        },
    )
    assert response.status_code == 200, (
        f"Expected status code 200 but got {response.status_code}. "
        + f"Response: {response.json()}"
    )
    assert "markdown_file" in response.json()
