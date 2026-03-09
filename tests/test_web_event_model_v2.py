def test_event_model_v2_supports_tool_artifact_task_interrupt_families():
    from nanobot.web.models import AgentEvent

    event = AgentEvent(
        type="tool.started",
        session_id="sess_1",
        run_id="run_1",
        timestamp="2026-03-09T10:30:00+08:00",
        payload={"tool_name": "read_file"},
    )
    assert event.type == "tool.started"
