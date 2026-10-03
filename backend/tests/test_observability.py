import sqlite3

import pytest

from backend.app import observability


@pytest.fixture()
def telemetry(tmp_path, monkeypatch):
    monkeypatch.setattr(observability, "database_path", tmp_path / "telemetry.db")
    observability._metrics.clear()
    observability.initialize_observability()
    return observability


def test_sensitive_values_are_redacted_recursively(telemetry):
    assert telemetry.redact({"api_key": "value", "nested": {"safe": "yes"}}) == {
        "api_key": "[REDACTED]", "nested": {"safe": "yes"}
    }
    assert "actual" not in telemetry.redact("token=actual")


def test_invalid_correlation_id_is_replaced(telemetry):
    context = telemetry.start_request("GET", "/health", "bad")
    assert context["correlation_id"].startswith("corr_")
    assert len(context["trace_id"]) == 32
    assert len(context["span_id"]) == 16


def test_valid_trace_context_is_propagated(telemetry):
    trace_id = "a" * 32
    context = telemetry.start_request(
        "GET", "/health", "correlation-123", f"00-{trace_id}-{'b' * 16}-01"
    )
    assert context["trace_id"] == trace_id
    assert context["correlation_id"] == "correlation-123"


def test_sampled_trace_is_persisted_and_exported(telemetry):
    telemetry.update_config(True, True, True, 1, 100, "admin")
    context = telemetry.start_request("POST", "/tool-requests", "correlation-123")
    telemetry.finish_request(context, 201)
    exported = telemetry.otlp_export()
    span = exported["resourceSpans"][0]["scopeSpans"][0]["spans"][0]
    assert span["traceId"] == context["trace_id"]
    assert span["name"] == "POST /tool-requests"


def test_zero_sampling_stores_no_trace(telemetry):
    telemetry.update_config(True, True, True, 0, 100, "admin")
    telemetry.finish_request(telemetry.start_request("GET", "/health"), 200)
    with sqlite3.connect(telemetry.database_path) as connection:
        assert connection.execute("SELECT COUNT(*) FROM observability_spans").fetchone()[0] == 0


def test_prometheus_metrics_have_no_sensitive_headers(telemetry):
    context = telemetry.start_request("GET", "/health?token=actual")
    telemetry.finish_request(context, 200)
    metrics = telemetry.prometheus_metrics()
    assert "greyguard_http_requests_total" in metrics
    assert "actual" not in metrics
    assert "[REDACTED]" in metrics


def test_configuration_bounds_are_enforced(telemetry):
    with pytest.raises(ValueError, match="sample rate"):
        telemetry.update_config(True, True, True, 1.1, 100, "admin")
    with pytest.raises(ValueError, match="retention"):
        telemetry.update_config(True, True, True, 0.5, 10, "admin")


def test_request_correlation_continues_across_lifecycle_routes(telemetry):
    telemetry.bind_request("request-123", "correlation-lifecycle")
    context = telemetry.start_request(
        "POST", "/tool-requests/request-123/decision"
    )
    assert context["correlation_id"] == "correlation-lifecycle"
