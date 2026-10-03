from backend.app.live_events import encode_sse, prepare_stream_events, recovery_events


def test_recovery_returns_only_newer_events():
    events = [{"event_id": "new"}, {"event_id": "last"}, {"event_id": "old"}]
    assert recovery_events(events, "last") == [{"event_id": "new"}]


def test_recovery_falls_back_when_cursor_is_outside_retention():
    events = [{"event_id": "new"}]
    assert recovery_events(events, "missing") == events


def test_sse_encoder_preserves_recovery_cursor():
    encoded = encode_sse("greyguard-event", {"status": "ok"}, "event-42")
    assert "id: event-42" in encoded
    assert "event: greyguard-event" in encoded

def test_stream_redacts_nested_credentials():
    events = [{"event_id": "one", "agent_name": "alpha", "details": {"api_key": "exposed", "nested": {"token": "value"}}}]
    result = prepare_stream_events(events, None)
    assert result[0]["details"]["api_key"] == "[REDACTED]"
    assert "exposed" not in str(result)

def test_agent_filter_cannot_leak_another_agent():
    events = [{"event_id": "one", "agent_name": "alpha"}, {"event_id": "two", "agent_name": "beta"}]
    assert prepare_stream_events(events, "alpha") == [{"event_id": "one", "agent_name": "alpha"}]
