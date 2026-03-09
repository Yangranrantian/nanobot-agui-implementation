from fastapi.testclient import TestClient


class FakeEventRuntime:
    def __init__(self) -> None:
        self.session_id = "sess_events"

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

    async def stream_session_events(self, _session_id: str):
        yield {"type": "message.completed", "content": "hello"}


def test_session_events_stream_message_lifecycle():
    from nanobot.web.api import create_app

    client = TestClient(create_app(runtime=FakeEventRuntime()))
    session_id = client.post("/sessions", json={}).json()["session_id"]

    with client.stream("GET", f"/sessions/{session_id}/events") as response:
        body = b"".join(response.iter_bytes())

    assert response.status_code == 200
    assert b"message.completed" in body
