import asyncio
import json
from types import SimpleNamespace

import pytest
from unittest.mock import MagicMock, patch, Mock

from ltc_client.helpers import (
    ProgressListener,
    async_job_monitor,
    Job,
    Machine,
    TqdmUpTo,
    monitor_jobs,
    make_stomp_connection,
)
from ltc_client.api import JOB_STATUS, STATUS_JOB


@pytest.fixture
def mock_websocket():
    """Mock WebSocket connection"""
    return Mock()


@pytest.fixture
def mock_stomp_connection():
    """Mock STOMP connection"""
    mock = Mock()
    mock.connect = Mock()
    return mock


def test_make_stomp_connection(mock_websocket, mock_stomp_connection):
    """Test the make_stomp_connection function creates and returns a proper connection."""

    # Test configuration
    test_config = {
        "protocol": "ws",
        "host": "test.example.com",
        "port": 15674,
        "user": "testuser",
        "password": "testpass",
    }

    # Set up our mocks
    with patch(
        "ltc_client.helpers.create_connection", return_value=mock_websocket
    ) as mock_create:
        with patch(
            "ltc_client.helpers.StompConnection",
            return_value=mock_stomp_connection,
        ) as mock_stomp:

            # Call the function
            conn = make_stomp_connection(test_config)

            # Verify create_connection was called with the correct URL
            mock_create.assert_called_once_with("ws://test.example.com:15674/ws")

            # Verify StompConnection was created with our WebSocket
            mock_stomp.assert_called_once_with(connector=mock_websocket)

            # Verify connect was called with credentials
            mock_stomp_connection.connect.assert_called_once_with(
                login="testuser", passcode="testpass"
            )

            # Verify the connection was returned
            assert conn == mock_stomp_connection


def test_make_stomp_connection_handles_connection_error(mock_websocket):
    """Test that connection errors are properly handled."""

    test_config = {
        "protocol": "ws",
        "host": "test.example.com",
        "port": 15674,
        "user": "testuser",
        "password": "testpass",
    }

    # Mock create_connection to raise an exception
    with patch(
        "ltc_client.helpers.create_connection",
        side_effect=ConnectionError("Failed to connect"),
    ) as mock_create:
        with pytest.raises(ConnectionError) as exc_info:
            make_stomp_connection(test_config)

        assert "Failed to connect" in str(exc_info.value)


def test_make_stomp_connection_invalid_config():
    """Test that invalid configurations raise the appropriate error."""

    # Missing required fields
    invalid_config = {
        "protocol": "ws",
        "host": "test.example.com",
        # Missing port
        "user": "testuser",
        "password": "testpass",
    }

    with pytest.raises(KeyError):
        make_stomp_connection(invalid_config)


@pytest.mark.asyncio
async def test_monitor_jobs_handles_dict_returns():
    """Test that monitor_jobs correctly handles dictionary returns from update_job_status."""

    # Dummy API: update_job_status returns a dict, not a coroutine
    class DummyAPI:
        def update_job_status(self, job_id, status):
            # Return a dictionary instead of a coroutine
            return {"job_id": job_id, "status": status}

        def get_job(self, job_id):
            return {"status": JOB_STATUS["Complete"]}

    api = DummyAPI()

    # Dummy connection
    class DummyConnection:
        def __init__(self):
            self.listeners = []
            self.subscriptions = []

        def add_listener(self, listener):
            self.listeners.append(listener)

        def subscribe(self, destination, id):
            self.subscriptions.append((destination, id))

        def unsubscribe(self, id):
            pass

        def remove_listener(self, listener):
            if listener in self.listeners:
                self.listeners.remove(listener)

    conn = DummyConnection()

    # Create test jobs
    job1 = Job(Machine({}, {}, {}), {}, {}, title="test-job-1")
    job1.id = "job-123"
    job2 = Job(Machine({}, {}, {}), {}, {}, title="test-job-2")
    job2.id = "job-456"
    jobs = [job1, job2]

    # Mock TqdmUpTo to avoid progress bar display
    class DummyPbar:
        def __init__(self, total, desc, leave=True):
            self.total = total
            self.desc = desc
            self.n = 0

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def update(self, n=1):
            self.n += n

    with patch("ltc_client.helpers.TqdmUpTo", DummyPbar):
        # This would have failed with "TypeError: unhashable type: 'dict'"
        # with the original implementation using asyncio.gather()
        monitor_task = asyncio.create_task(monitor_jobs(api, jobs, conn))

        # Let the function start and register listeners
        await asyncio.sleep(0.1)

        # Find the registered listener
        assert len(conn.listeners) > 0, "No listener registered"
        listener = conn.listeners[0]

        # Simulate completion messages for both jobs
        for job in jobs:
            headers = [(b"destination", f"/topic/{job.id}.worker.progress".encode())]
            payload = {"status": JOB_STATUS["Complete"]}
            message = json.dumps(payload).encode()
            frame = SimpleNamespace(header=headers, message=message)
            listener.on_message(frame)

        # Wait for monitor to complete
        result = await asyncio.wait_for(monitor_task, timeout=2.0)

        # Verify results
        assert len(result) == 2
        assert result[job1.id] == STATUS_JOB[JOB_STATUS["Complete"]]
        assert result[job2.id] == STATUS_JOB[JOB_STATUS["Complete"]]


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
