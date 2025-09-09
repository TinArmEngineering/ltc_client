import asyncio
import json
from types import SimpleNamespace

import pytest
from unittest.mock import MagicMock

from ltc_client.helpers import (
    ProgressListener,
    async_job_monitor,
    Job,
    Machine,
    TqdmUpTo,
)
from ltc_client.api import JOB_STATUS, STATUS_JOB


def test_progress_listener_parses_time_prefixed_json():
    job = MagicMock(id="job-1")
    uid = "uid-123"
    pl = ProgressListener(job, uid)

    called = {}

    def cb(
        done, tsize=None, worker=None, message_type=None
    ):  # Add message_type parameter
        called["args"] = (
            done,
            tsize,
            worker,
        )  # Keep original tuple format for assertion

    pl.callback_fn = cb

    headers = [
        (b"subscription", uid.encode()),
        (b"destination", f"/topic/{job.id}.worker.solver.progress".encode()),
    ]
    payload = {"job_id": job.id, "status": JOB_STATUS["Complete"]}
    # time prefix + level + json
    message = f"23:46:46 - PROGRESS - {json.dumps(payload)}".encode()
    frame = SimpleNamespace(header=headers, message=message)

    pl.on_message(frame)

    assert "args" in called
    # listener forwards numeric status as first arg; worker extracted from destination
    assert called["args"] == (JOB_STATUS["Complete"], None, "worker")


@pytest.mark.asyncio
async def test_async_job_monitor_stops_on_status_message(monkeypatch):
    # Dummy API: update_job_status no-op, get_job returns Complete at end
    class DummyAPI:
        def update_job_status(self, job_id, status):
            return None

        def get_job(self, job_id):
            return {"status": JOB_STATUS["Complete"]}

    api = DummyAPI()

    # Dummy connection: store listeners so test can call .on_message(...)
    class DummyConnection:
        def __init__(self):
            self.listeners = []
            self.subscriptions = []

        def add_listener(self, listener):
            self.listeners.append(listener)

        def subscribe(self, destination, id):
            self.subscriptions.append((destination, id))

    conn = DummyConnection()

    # Stub out TqdmUpTo to avoid real progress UI
    class DummyPbar:
        def __init__(self, total, desc, position, leave=False):
            self.total = total
            self.desc = desc
            self.position = position
            self.n = 0

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def update_to(self, b=1, bsize=1, tsize=None):
            if tsize is not None:
                self.total = tsize
            self.n = b * bsize

        def refresh(self):
            pass

    monkeypatch.setattr("ltc_client.helpers.TqdmUpTo", DummyPbar)

    # Create job and start monitor in background
    job = Job(Machine({}, {}, {}), {}, {}, title="t-test")
    job.id = "job-123"

    monitor_task = asyncio.create_task(async_job_monitor(api, job, conn, position=0))

    # allow monitor to run and register listener
    await asyncio.sleep(0)

    # find the registered listener
    assert conn.listeners, "listener was not registered"
    listener = conn.listeners[0]

    # Compose a progress frame that contains a server-side status message (json)
    payload = {"job_id": job.id, "status": JOB_STATUS["Complete"]}
    message = f"23:46:46 - PROGRESS - {json.dumps(payload)}".encode()
    headers = [
        (b"subscription", listener.uid.encode()),  # must match listener uid
        (b"destination", f"/topic/{job.id}.worker.solver.progress".encode()),
    ]
    frame = SimpleNamespace(header=headers, message=message)

    # deliver the frame (synchronous call into listener)
    listener.on_message(frame)

    # await monitor completion and assert returned status name
    result = await asyncio.wait_for(monitor_task, timeout=2.0)
    assert result == STATUS_JOB[JOB_STATUS["Complete"]]


def test_listener_accepts_frame_when_subscription_missing():
    job = MagicMock(id="job-1")
    uid = "uid-123"
    pl = ProgressListener(job, uid)

    called = {}

    def cb(
        done, tsize=None, worker=None, message_type=None
    ):  # Add message_type parameter
        called["args"] = (
            done,
            tsize,
            worker,
        )  # Keep original tuple format for assertion

    pl.callback_fn = cb

    # simulate broker not setting subscription header but correct destination
    headers = [
        # subscription intentionally wrong / missing
        (b"subscription", b"other-sub"),
        (b"destination", f"/topic/{job.id}.worker.solver.progress".encode()),
    ]
    payload = {"job_id": job.id, "status": JOB_STATUS["Complete"]}
    message = f"23:46:46 - PROGRESS - {json.dumps(payload)}".encode()
    frame = SimpleNamespace(header=headers, message=message)

    pl.on_message(frame)

    assert "args" in called
    assert called["args"] == (JOB_STATUS["Complete"], None, "worker")
