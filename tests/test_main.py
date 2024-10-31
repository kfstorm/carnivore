from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_clip_url_to_markdown():
    response = client.post(
        "/clip",
        json={"url": "https://blog.omnivore.app/p/omnivore-is-joining-elevenlabs"},
    )
    assert response.status_code == 200
    assert "markdown_file" in response.json()
