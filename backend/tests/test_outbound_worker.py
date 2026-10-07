import asyncio

from backend.app import outbound_worker as worker


def test_disabled_by_default_under_pytest(monkeypatch):
    monkeypatch.delenv("GREYGUARD_DELIVERY_WORKER_ENABLED", raising=False)
    assert worker._running_under_pytest() is True
    assert worker._enabled() is False


def test_explicit_true_overrides_the_pytest_default(monkeypatch):
    monkeypatch.setenv("GREYGUARD_DELIVERY_WORKER_ENABLED", "true")
    assert worker._enabled() is True


def test_explicit_false_disables_outside_pytest(monkeypatch):
    monkeypatch.setenv("GREYGUARD_DELIVERY_WORKER_ENABLED", "false")
    assert worker._enabled() is False


def test_interval_and_batch_limit_fall_back_on_bad_values(monkeypatch):
    monkeypatch.setenv("GREYGUARD_DELIVERY_INTERVAL_SECONDS", "not-a-number")
    assert worker._interval_seconds() == 15.0
    monkeypatch.setenv("GREYGUARD_DELIVERY_BATCH_LIMIT", "not-a-number")
    assert worker._batch_limit() == 25


def test_interval_and_batch_limit_respect_valid_overrides(monkeypatch):
    monkeypatch.setenv("GREYGUARD_DELIVERY_INTERVAL_SECONDS", "5")
    assert worker._interval_seconds() == 5.0
    monkeypatch.setenv("GREYGUARD_DELIVERY_BATCH_LIMIT", "3")
    assert worker._batch_limit() == 3


def test_run_tick_survives_a_subsystem_raising(monkeypatch):
    # Every real process_* function already turns its own failures into QUEUED/DEAD_LETTER state
    # before raising anything to this layer, so only a truly unexpected error reaches here - and
    # even that must not stop the other three subsystems from getting their turn.
    calls = []

    def _boom(**_kwargs):
        calls.append("notification")
        raise RuntimeError("database unavailable")

    def _ok(**_kwargs):
        calls.append("ok")
        return {"processed": 0}

    monkeypatch.setattr(worker, "process_deliveries", lambda sender, limit, worker_id: _boom())
    monkeypatch.setattr(worker, "process_incidents", lambda sender, limit, worker_id: _ok())
    monkeypatch.setattr(worker, "process_queue", lambda sender, limit, worker_id: _ok())
    monkeypatch.setattr(worker, "run_due_schedules", lambda notifier, limit, worker_id: _ok())
    worker._run_tick()
    assert calls == ["notification", "ok", "ok", "ok"]


def test_start_and_stop_worker_round_trip(monkeypatch):
    monkeypatch.setenv("GREYGUARD_DELIVERY_WORKER_ENABLED", "true")
    monkeypatch.setenv("GREYGUARD_DELIVERY_INTERVAL_SECONDS", "60")
    ticks = []
    monkeypatch.setattr(worker, "_run_tick", lambda: ticks.append(1))

    async def _scenario():
        task, stop_event = worker.start_worker()
        assert task is not None
        await asyncio.sleep(0.05)
        await worker.stop_worker(task, stop_event, grace_seconds=5.0)
        assert task.done()

    asyncio.run(_scenario())
    assert ticks  # the loop ran at least once before being told to stop


def test_start_worker_returns_nothing_when_disabled(monkeypatch):
    monkeypatch.delenv("GREYGUARD_DELIVERY_WORKER_ENABLED", raising=False)
    task, stop_event = worker.start_worker()
    assert task is None and stop_event is None
