def test_task_events_project_into_status_panel():
    from nanobot.web.runtime import project_status_from_events

    status = project_status_from_events([
        {"type": "task.started", "payload": {"task_id": "t1", "title": "Analyze repo"}}
    ])
    assert status["active_task_count"] == 1
