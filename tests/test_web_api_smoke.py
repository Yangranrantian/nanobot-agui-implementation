import pytest
from fastapi.testclient import TestClient


class FakeDispatchRuntime:
    def __init__(self, session_id: str = "sess_fake") -> None:
        self.session_id = session_id
        self.dispatched: list[dict] = []

    def create_session(self):
        return {
            "session_id": self.session_id,
            "session_key": f"web:{self.session_id}",
            "created_at": "2026-03-08T00:00:00",
            "updated_at": "2026-03-08T00:00:00",
        }

    def list_sessions(self):
        return {"items": [self.create_session()]}

    def get_messages(self, _session_id: str):
        return {"items": []}

    async def dispatch_message(self, session_id: str, content: str, attachments: list[dict]):
        self.dispatched.append(
            {
                "session_id": session_id,
                "content": content,
                "attachments": attachments,
            }
        )
        return {
            "run_id": "run_001",
            "session_id": session_id,
            "status": "accepted",
        }


def test_web_runtime_exposes_session_routes():
    from nanobot.web.api import create_app

    app = create_app()

    assert app is not None


@pytest.fixture
def client(tmp_path):
    from nanobot.web.api import create_app
    from nanobot.web.runtime import WebRuntime

    app = create_app(runtime=WebRuntime(tmp_path))
    return TestClient(app)


@pytest.fixture
def fake_runtime():
    return FakeDispatchRuntime()


def test_create_and_list_sessions(client):
    created = client.post("/sessions", json={})
    assert created.status_code == 200

    listed = client.get("/sessions")
    assert listed.status_code == 200
    assert len(listed.json()["items"]) == 1


def test_get_session_messages_returns_history(client):
    session_id = client.post("/sessions", json={}).json()["session_id"]

    resp = client.get(f"/sessions/{session_id}/messages")

    assert resp.status_code == 200
    assert resp.json()["items"] == []


def test_send_message_starts_agent_run(fake_runtime):
    from nanobot.web.api import create_app

    client = TestClient(create_app(runtime=fake_runtime))
    session_id = client.post("/sessions", json={}).json()["session_id"]

    resp = client.post(
        f"/sessions/{session_id}/messages",
        json={"content": "hello", "attachments": []},
    )

    assert resp.status_code == 202
    assert fake_runtime.dispatched == [
        {
            "session_id": session_id,
            "content": "hello",
            "attachments": [],
        }
    ]



def test_web_runtime_allows_browser_cors(client):
    response = client.options(
        "/sessions",
        headers={
            "Origin": "http://127.0.0.1:4173",
            "Access-Control-Request-Method": "POST",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "*"
