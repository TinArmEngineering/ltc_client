from .api import Quantity, NameQuantityPair
from .api import JOB_STATUS, STATUS_JOB

import pint
from webstompy import StompListener, StompConnection
from websocket import create_connection
import numpy as np
import logging
import asyncio
import json
from dataclasses import dataclass
from uuid import uuid4
from typing import Any, Callable, Dict, List, Literal, Optional, Tuple


logger = logging.getLogger(__name__)

q = pint.get_application_registry()


@dataclass
class ProgressEvent:
    """Structured progress event emitted by :class:`ProgressListener`.

    Attributes
    ----------
    job_id : str
        The job identifier this event belongs to.
    worker : str
        The worker name that produced this event.
    kind : str
        One of ``"progress"``, ``"status"``, ``"remaining"``, or
        ``"time_remaining"``.
    done : float, optional
        Units completed so far (for ``"progress"`` / ``"remaining"``).
    total : float, optional
        Total units (for ``"progress"`` / ``"remaining"``).
    status : int, optional
        Numeric job-status code (for ``"status"`` events).
    status_name : str, optional
        Human-readable status name (for ``"status"`` events).
    remaining_time : str, optional
        Remaining time string (for ``"time_remaining"`` events).
    raw : dict, optional
        The raw parsed JSON payload from the STOMP frame.
    """

    job_id: str
    worker: str
    kind: Literal["progress", "status", "remaining", "time_remaining"]
    done: Optional[float] = None
    total: Optional[float] = None
    status: Optional[int] = None
    status_name: Optional[str] = None
    remaining_time: Optional[str] = None
    raw: Optional[dict] = None


def decode(enc: dict) -> "pint.Quantity":
    """Decode a quantity encoded object

    Parameters
    ----------
    enc : dict
        The encoded object

    Returns
    -------
    pint.Quantity
        The decoded quantity object
    """

    units_data = enc.get("units") or ()
    units_tuple: Tuple[Tuple[str, int], ...] = tuple(
        (e["name"], e["exponent"]) for e in units_data
    )

    # magnitude can be a single value or an array represented as a list
    if len(enc["magnitude"]) != 1:
        enc_tuple: Tuple[Any, Tuple[Tuple[str, int], ...]] = (
            np.array(enc["magnitude"], dtype=np.float64).reshape(enc["shape"]),
            units_tuple,
        )
    else:
        enc_tuple = (enc["magnitude"][0], units_tuple)

    try:
        quant: "pint.Quantity" = q.Quantity.from_tuple(enc_tuple)
        # quant.ito_base_units()
    except Exception as exc:
        logger.error(
            "Error decoding %s with units %s: %s",
            enc.get("magnitude"),
            enc.get("units"),
            exc,
        )
        raise

    logger.debug("convert %s -> %s", enc, quant)
    return quant


def encode(quantity: "pint.Quantity") -> dict:
    """Encode a pint.Quantity object into a serializable dict

    Parameters
    ----------
    quantity : pint.Quantity
        The quantity to encode

    Returns
    -------
    dict
        The encoded quantity object
    """

    units_list = []
    for unit_name, exponent in quantity.units._units.items():
        units_list.append({"name": unit_name, "exponent": exponent})

    if isinstance(quantity.magnitude, np.ndarray):
        magnitude_list = quantity.magnitude.flatten().tolist()
        shape = quantity.magnitude.shape
    else:
        magnitude_list = [float(quantity.magnitude)]
        shape = ()

    enc = {
        "magnitude": magnitude_list,
        "units": units_list,
        "shape": shape,
        "unit_string": f"{quantity.units:~P}",
    }

    logger.debug("convert %s -> %s", quantity, enc)
    return enc


class Machine(object):
    def __init__(self, stator, rotor, winding, materials=None):

        self.stator = stator
        self.rotor = rotor
        self.winding = winding
        if materials is not None:
            self.materials = materials
        else:
            self.materials = {
                "rotor_lamination": "66018e5d1cd3bd0d3453646f",  # default M230-35A
                "rotor_magnet": "66018e5b1cd3bd0d3453646c",  # default is N35UH
                "rotor_air_L": "6602fb42c4a87c305481e8a6",
                "rotor_air_R": "6602fb42c4a87c305481e8a6",
                "rotor_banding": "6602fb42c4a87c305481e8a6",
                "stator_lamination": "66018e5d1cd3bd0d3453646f",  # default M230-35A
                "stator_slot_wedge": "6602fb7239bfdea291a25dd7",
                "stator_slot_liner": "6602fb5166d3c6adaa8ebe8c",
                "stator_slot_winding": "66018e5d1cd3bd0d34536470",
                "stator_slot_potting": "6602fd41b8e866414fe983ec",
            }

    def __repr__(self) -> str:
        return f"Machine({self.stator}, {self.rotor}, {self.winding})"

    def to_api(self):
        stator_api = [
            NameQuantityPair("stator", k, Quantity(*self.stator[k].to_tuple()))
            for k in self.stator
        ]
        rotor_api = [
            NameQuantityPair("rotor", k, Quantity(*self.rotor[k].to_tuple()))
            for k in self.rotor
        ]
        winding_api = [
            NameQuantityPair("winding", k, Quantity(*self.winding[k].to_tuple()))
            for k in self.winding
        ]
        data = []
        data.extend(list(x.to_dict() for x in stator_api))
        data.extend(list(x.to_dict() for x in rotor_api))
        data.extend(list(x.to_dict() for x in winding_api))
        return data


def make_stomp_connection(stomp_conf):
    """Create and establish a STOMP connection over WebSocket.

    This function sets up a WebSocket connection to a STOMP server using the provided
    configuration, and returns a connected STOMP client.

    Parameters
    ----------
    stomp_conf : dict
        Dictionary containing STOMP connection configuration with keys:
        - protocol: Connection protocol (e.g. 'ws', 'wss')
        - host: Hostname or IP address
        - port: Connection port number
        - user: Username for authentication
        - password: Password for authentication

    Returns
    -------
    webstompy.StompConnection
        A connected STOMP client instance

    Raises
    ------
    ConnectionError
        If the connection to the STOMP server fails
    ValueError
        If the configuration parameters are invalid

    Examples
    --------
    >>> stomp_conf = {
    ...     "protocol": "ws",
    ...     "host": "localhost",
    ...     "port": 15674,
    ...     "user": "guest",
    ...     "password": "guest"
    ... }
    >>> connection = make_stomp_connection(stomp_conf)
    """
    ws_echo = create_connection(
        f"{stomp_conf['protocol']}://{stomp_conf['host']}:{stomp_conf['port']}/ws"
    )
    connection = StompConnection(connector=ws_echo)
    connection.connect(login=stomp_conf["user"], passcode=stomp_conf["password"])

    return connection


class ProgressListener(StompListener):
    def __init__(self, job, uid):
        self.job_id = job.id
        self.uid = uid
        self._callback_fn = None  # Initialize the callback function

    @property
    def callback_fn(self):
        return self._callback_fn

    @callback_fn.setter
    def callback_fn(self, fn):
        self._callback_fn = fn

    def on_message(self, frame):
        logger.debug("ProgressListener.on_message START frame=%r", frame)
        try:
            headers = {key.decode(): value.decode() for key, value in frame.header}
            sub_hdr = headers.get("subscription")
            dest_hdr = headers.get("destination", "")
            # accept if subscription matches OR destination is for our job topic (some brokers don't preserve subscription)
            if sub_hdr != self.uid and not dest_hdr.startswith(f"/topic/{self.job_id}"):
                logger.debug(
                    "Ignoring frame: subscription=%r uid=%r destination=%r payload=%r",
                    sub_hdr,
                    self.uid,
                    dest_hdr,
                    getattr(frame, "message", None),
                )
                return

            try:
                destination = headers.get("destination", "")
                parts = destination.split(".")
                worker_name = "unknown"
                if len(parts) > 1 and parts[0] == f"/topic/{self.job_id}":
                    worker_name = parts[1]

                raw = (
                    frame.message.decode()
                    if isinstance(frame.message, (bytes, bytearray))
                    else str(frame.message)
                )

                # Support two formats:
                # 1) "<time> - <LEVEL> - <json>"
                # 2) "<json>"
                if " - " in raw:
                    _, _level_str, mesg_str = raw.split(" - ", 2)
                    payload = mesg_str.strip()
                else:
                    payload = raw.strip()

                # Log the raw message
                logger.debug(f"Received message from {worker_name}: {payload}")
                # Expect valid JSON payload — try to parse and fail if not JSON
                data = json.loads(payload)
                logger.debug(f"Parsed message data: {data}")
            except (ValueError, IndexError, json.JSONDecodeError) as exc:
                logger.warning(
                    "Unable to process progress message: %s (%s)",
                    getattr(frame, "message", frame),
                    exc,
                )
                return

            # forward to callback if present
            if not self._callback_fn:
                return

            # Emit a structured ProgressEvent for each recognised message type.
            if isinstance(data, dict):
                if "done" in data:
                    logger.debug(
                        "Progress update: done=%s, total=%s",
                        data["done"],
                        data.get("total"),
                    )
                    self._callback_fn(
                        ProgressEvent(
                            job_id=self.job_id,
                            worker=worker_name,
                            kind="progress",
                            done=data["done"],
                            total=data.get("total"),
                            raw=data,
                        )
                    )
                    return

                # Server-side status codes
                if "status" in data:
                    try:
                        status_val = int(data["status"])
                        logger.debug(
                            "Status message received: %s, Complete threshold: %s",
                            status_val,
                            JOB_STATUS["Complete"],
                        )
                    except Exception:
                        status_val = data["status"]
                        logger.exception("Non-integer status received: %r", status_val)
                    self._callback_fn(
                        ProgressEvent(
                            job_id=self.job_id,
                            worker=worker_name,
                            kind="status",
                            status=status_val,
                            status_name=STATUS_JOB.get(status_val),
                            raw=data,
                        )
                    )
                    return

                # remaining percent style
                if "remaining" in data and "unit" in data:
                    try:
                        remaining = float(data.get("remaining") or 0.0)
                        unit = data.get("unit", "")

                        if unit in ("seconds", "second"):
                            logger.debug(
                                "Time remaining update: %s %s", remaining, unit
                            )
                            self._callback_fn(
                                ProgressEvent(
                                    job_id=self.job_id,
                                    worker=worker_name,
                                    kind="time_remaining",
                                    remaining_time=f"{remaining:.1f} {unit}",
                                    raw=data,
                                )
                            )
                        else:
                            done = max(0, min(100, int(round(100.0 - remaining))))
                            logger.debug(
                                "Remaining percent update: remaining=%s, done=%s",
                                remaining,
                                done,
                            )
                            self._callback_fn(
                                ProgressEvent(
                                    job_id=self.job_id,
                                    worker=worker_name,
                                    kind="remaining",
                                    done=done,
                                    total=100,
                                    raw=data,
                                )
                            )
                    except Exception as e:
                        logger.debug(
                            "Could not interpret remaining value: %s (%s)",
                            data.get("remaining"),
                            e,
                        )
                        return

            logger.debug("ProgressListener parsed frame -> %r", frame)
        except Exception:
            logger.exception("ProgressListener failed handling frame=%r", frame)
            raise
        finally:
            logger.debug("ProgressListener.on_message END frame=%r", frame)


class TqdmProgressReporter:
    """Renders :class:`ProgressEvent` updates using a ``tqdm`` progress bar.

    This is an optional adapter that sits on top of the event-based monitoring
    core. It is suitable for plain Python scripts and Jupyter notebooks.  Pass
    an instance as the ``progress_callback`` argument of
    :func:`async_job_monitor` or :func:`monitor_jobs` to get the familiar
    ``tqdm`` progress display.

    Parameters
    ----------
    desc : str
        Progress bar description label.
    total : float
        Total units for the progress bar.
    position : int
        Vertical position of the bar (for multiple concurrent bars).
    leave : bool
        Whether to leave the bar visible after completion.

    Examples
    --------
    >>> reporter = TqdmProgressReporter(desc="My job", position=0)
    >>> await async_job_monitor(api, job, conn, progress_callback=reporter)
    >>> reporter.close()
    """

    def __init__(
        self,
        desc: str = "Job",
        total: float = 100,
        position: int = 0,
        leave: bool = False,
    ):
        from tqdm.auto import tqdm

        self._bar = tqdm(total=total, desc=desc, position=position, leave=leave)

    def __call__(self, event: "ProgressEvent") -> None:
        """Handle a single :class:`ProgressEvent`."""
        if event.kind in ("progress", "remaining") and event.done is not None:
            if event.total is not None and self._bar.total != event.total:
                self._bar.total = event.total
            new_n = max(self._bar.n, int(event.done))
            if new_n > self._bar.n:
                self._bar.update(new_n - self._bar.n)
            else:
                self._bar.refresh()
        elif event.kind == "time_remaining" and event.remaining_time:
            self._bar.set_postfix_str(f"ETA {event.remaining_time}")
        elif event.kind == "status" and event.status_name:
            self._bar.set_description(f"{self._bar.desc} [{event.status_name}]")

    def close(self) -> None:
        """Close the underlying tqdm bar."""
        self._bar.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


async def async_job_monitor(
    api,
    my_job,
    connection,
    position: int = 0,
    auto_start: bool = True,
    progress_callback: Optional[Callable[["ProgressEvent"], None]] = None,
):
    """Monitor a single job asynchronously and report progress.

    Parameters
    ----------
    api : Api
        API client instance.
    my_job : Job
        The job to monitor.
    connection : StompConnection
        Active STOMP connection for receiving progress frames.
    position : int, optional
        Vertical position for the tqdm bar when *progress_callback* is ``None``
        (default ``0``).
    auto_start : bool, optional
        Queue the job for meshing automatically (default ``True``).
    progress_callback : callable, optional
        A callable that accepts a single :class:`ProgressEvent` argument.  When
        ``None`` (default) a :class:`TqdmProgressReporter` is created
        automatically so that existing callers continue to see a progress bar.
        Pass a custom callable to receive structured events without any tqdm
        dependency (useful for marimo, Jupyter widgets, or silent operation).

    Returns
    -------
    str
        The final job status name (e.g. ``"Complete"``).
    """
    uid = str(uuid4())
    listener = ProgressListener(my_job, uid)
    connection.add_listener(listener)
    connection.subscribe(destination=f"/topic/{my_job.id}.*.*.progress", id=uid)

    done_event = asyncio.Event()

    # capture the running loop so listener (which may run in another thread)
    # can schedule callbacks safely on the asyncio loop.
    loop = asyncio.get_running_loop()

    # If no callback was supplied, use a tqdm reporter (preserves legacy UX).
    _owned_reporter: Optional[TqdmProgressReporter] = None
    if progress_callback is None:
        _owned_reporter = TqdmProgressReporter(
            desc=f"Job {my_job.title}",
            total=100,
            position=position,
            leave=False,
        )
        progress_callback = _owned_reporter

    def _on_progress(event: "ProgressEvent") -> None:
        try:
            if progress_callback is not None:
                progress_callback(event)
            # Mark the job done when a terminal status is received.
            if event.kind == "status" and event.status is not None:
                try:
                    if int(event.status) >= JOB_STATUS["Complete"]:
                        done_event.set()
                except Exception:
                    pass
        except Exception:
            logger.exception("Error in _on_progress handler")

    import functools

    def _cb_wrapper(event: "ProgressEvent") -> None:
        try:
            # Schedule actual handling on the asyncio loop thread.
            loop.call_soon_threadsafe(functools.partial(_on_progress, event))
        except Exception:
            logger.exception("Error scheduling _on_progress on event loop")

    # install the wrapper as the listener callback
    listener.callback_fn = _cb_wrapper
    logger.debug("async_job_monitor: listener and subscription installed")
    if auto_start:
        api.update_job_status(my_job.id, JOB_STATUS["QueuedForMeshing"])
    # Wait until done_event is set (by status >= complete)
    try:
        await done_event.wait()
    except asyncio.CancelledError:
        raise
    finally:
        # cleanup subscription/listener
        try:
            connection.unsubscribe(id=uid)
        except Exception:
            logger.debug("unsubscribe failed", exc_info=True)
        try:
            connection.remove_listener(listener)
        except Exception:
            logger.debug("remove_listener failed", exc_info=True)
        if _owned_reporter is not None:
            _owned_reporter.close()

    # final job status
    final_job_state = api.get_job(my_job.id)
    logger.debug(
        f"Final job status: {final_job_state['status']} ({STATUS_JOB[final_job_state['status']]})"
    )
    # Force set done_event to ensure we don't hang
    if not done_event.is_set():
        logger.debug("Forcing done_event to be set at end of job monitor")
        done_event.set()

    return STATUS_JOB[final_job_state["status"]]


try:
    _orig_async_job_monitor  # type: ignore[name-defined]
except NameError:
    _orig_async_job_monitor = None

# to re-export Material/Job for compatibility do a deferred import:
try:
    from .material import Material
    from .job import Job  # type: ignore
except Exception:
    logger.exception("Deferred import of Material/Job failed")
    raise


class JobBatchProgressListener(StompListener):
    """A STOMP listener that handles progress messages for a batch of jobs."""

    def __init__(self, job_ids: List[str], callback: Callable):
        self.job_ids = set(job_ids)
        self._callback = callback
        self.uid = str(uuid4())
        # Track message receipt to help diagnose issues
        self.last_message_time = None
        self.message_count = 0

    def on_message(self, frame):
        # Log every frame received regardless of content
        try:
            self.last_message_time = asyncio.get_running_loop().time()
        except RuntimeError:
            # Fallback if called outside a running loop (e.g., in tests)
            self.last_message_time = (
                asyncio.get_event_loop_policy().get_event_loop().time()
            )
        self.message_count += 1

        # Debug raw frame data
        raw_headers = (
            {
                k.decode() if isinstance(k, bytes) else str(k): (
                    v.decode() if isinstance(v, bytes) else str(v)
                )
                for k, v in frame.header
            }
            if hasattr(frame, "header")
            else {}
        )
        raw_body = (
            frame.message.decode()
            if hasattr(frame, "message")
            and isinstance(frame.message, (bytes, bytearray))
            else str(frame.message)
        )

        logger.debug(
            f"RAW STOMP FRAME: headers={raw_headers}, body_start={raw_body[:100]}..."
        )

        logger.debug("JobBatchProgressListener.on_message START frame=%r", frame)
        try:
            headers = {key.decode(): value.decode() for key, value in frame.header}
            dest_hdr = headers.get("destination", "")
            logger.debug(f"Processing message with destination: {dest_hdr}")

            # Extract job_id from destination topic: /topic/{job_id}.*
            try:
                parts = dest_hdr.split("/")
                if len(parts) < 3 or parts[1] != "topic":
                    logger.debug(
                        f"Skipping message with invalid topic format: {dest_hdr}"
                    )
                    return

                topic_parts = parts[2].split(".")
                if not topic_parts:
                    logger.debug(f"No job ID in topic: {dest_hdr}")
                    return

                job_id = topic_parts[0]
                logger.debug(f"Extracted job_id={job_id} from destination={dest_hdr}")
            except IndexError:
                logger.debug("Could not parse job_id from destination: %s", dest_hdr)
                return

            if job_id not in self.job_ids:
                logger.debug("Ignoring message for untracked job_id: %s", job_id)
                return

            # The rest of the message parsing is similar to ProgressListener
            try:
                raw = (
                    frame.message.decode()
                    if isinstance(frame.message, (bytes, bytearray))
                    else str(frame.message)
                )
                logger.debug(f"Raw message content: {raw[:200]}...")

                if " - " in raw:
                    time_str, level_str, mesg_str = raw.split(" - ", 2)
                    logger.debug(f"Parsed time={time_str}, level={level_str}")
                    payload = mesg_str.strip()
                else:
                    payload = raw.strip()

                data = json.loads(payload)
                logger.debug(f"Successfully parsed JSON: {data}")
            except (ValueError, IndexError, json.JSONDecodeError) as exc:
                logger.warning(
                    "Unable to process progress message: %s (%s)",
                    getattr(frame, "message", frame),
                    exc,
                )
                return

            # Forward job_id and parsed data to the callback
            logger.debug(f"Calling callback with job_id={job_id}, data={data}")
            self._callback(job_id, data)

        except Exception as e:
            logger.exception(
                "JobBatchProgressListener failed handling frame=%r: %s", frame, e
            )
        finally:
            logger.debug("JobBatchProgressListener.on_message END frame=%r", frame)


class _NullContext:
    """A no-op context manager used as a placeholder when tqdm is disabled."""

    def __enter__(self):
        return None

    def __exit__(self, *args):
        pass


async def monitor_jobs(
    api: "Api",
    jobs: List["Job"],
    connection,
    auto_start: bool = True,
    message_timeout: int = 30,
    progress_callback: Optional[Callable[["ProgressEvent"], None]] = None,
):
    """Monitor a batch of jobs asynchronously and report progress.

    Parameters
    ----------
    api : Api
        API client instance.
    jobs : List[Job]
        List of jobs to monitor.
    connection : StompConnection
        Active STOMP connection for receiving job updates.
    auto_start : bool, optional
        Queue all jobs for meshing automatically (default ``True``).
    message_timeout : int, optional
        Seconds of inactivity before monitoring is abandoned (default ``30``).
    progress_callback : callable, optional
        A callable that accepts a single :class:`ProgressEvent` argument.
        When ``None`` (default) a ``tqdm`` batch progress bar is displayed.
        Supply a custom callable to receive structured events and suppress the
        tqdm display — useful for marimo, Jupyter widgets, or silent operation.

    Returns
    -------
    Dict[str, str]
        Dictionary mapping job IDs to their final status names.  On timeout an
        extra ``"_monitoring_status": "TIMED_OUT"`` key is included.
    """
    logger.info(f"Starting batch monitoring for {len(jobs)} jobs")
    job_ids = [job.id for job in jobs]
    logger.debug(f"Job IDs: {job_ids}")

    # Check connection status
    if hasattr(connection, "is_connected") and callable(connection.is_connected):
        conn_status = connection.is_connected()
        logger.info(f"STOMP connection status: {conn_status}")
    else:
        logger.warning(
            "Unable to check STOMP connection status - no is_connected() method"
        )

    job_status_events: Dict[str, asyncio.Event] = {
        job_id: asyncio.Event() for job_id in job_ids
    }

    # Track status for each job
    job_statuses = {job_id: "Preparing" for job_id in job_ids}

    # Track last activity timestamp
    loop = asyncio.get_running_loop()
    last_activity = loop.time()

    # Set up status counters for display
    status_counts = {status_name: 0 for status_name in STATUS_JOB.values()}
    status_counts["Preparing"] = len(jobs)

    def update_status_counts():
        """Update the counter of jobs in each status."""
        for status in status_counts:
            status_counts[status] = 0
        for status in job_statuses.values():
            if status in status_counts:
                status_counts[status] += 1
            else:
                status_counts[status] = 1
        logger.debug(
            f"Current job status counts: {', '.join([f'{s}:{c}' for s, c in status_counts.items() if c > 0])}"
        )

    def _on_message(job_id: str, data: dict):
        nonlocal last_activity

        # Always update activity timestamp for any message
        last_activity = loop.time()
        logger.debug(f"Message received for job {job_id}: {data}")

        # Handle status updates
        if "status" in data:
            try:
                status_val = int(data["status"])
                status_name = STATUS_JOB.get(status_val, "Unknown")
                logger.info(f"Job {job_id} status update: {status_val} ({status_name})")

                # Update job status
                job_statuses[job_id] = status_name
                update_status_counts()

                # Emit structured event if a callback was supplied.
                if progress_callback is not None:
                    try:
                        progress_callback(
                            ProgressEvent(
                                job_id=job_id,
                                worker="",
                                kind="status",
                                status=status_val,
                                status_name=status_name,
                                raw=data,
                            )
                        )
                    except Exception:
                        logger.exception("Error in progress_callback")

                # If job is complete or beyond, set its event
                if status_val >= JOB_STATUS["Complete"]:
                    logger.info(
                        f"Job {job_id} marked as complete with status {status_name}"
                    )
                    loop.call_soon_threadsafe(job_status_events[job_id].set)
            except (ValueError, KeyError) as e:
                logger.warning(f"Invalid status value for job {job_id}: {e}")

        # Handle "done"/"total" progress updates
        elif "done" in data and "total" in data:
            try:
                done = data["done"]
                total = data.get("total", 100)
                logger.debug(f"Job {job_id} progress: {done}/{total}")
                if progress_callback is not None:
                    try:
                        progress_callback(
                            ProgressEvent(
                                job_id=job_id,
                                worker="",
                                kind="progress",
                                done=done,
                                total=total,
                                raw=data,
                            )
                        )
                    except Exception:
                        logger.exception("Error in progress_callback")
            except (ValueError, TypeError) as e:
                logger.warning(f"Error parsing done/total for job {job_id}: {e}")

        # Handle "remaining" style progress updates (important for solver)
        elif "remaining" in data and "unit" in data:
            try:
                remaining = float(data.get("remaining") or 0.0)
                unit = data.get("unit", "")

                if unit in ("seconds", "second"):
                    logger.debug(f"Job {job_id}: Time remaining: {remaining} {unit}")
                    if progress_callback is not None:
                        try:
                            progress_callback(
                                ProgressEvent(
                                    job_id=job_id,
                                    worker="",
                                    kind="time_remaining",
                                    remaining_time=f"{remaining:.1f} {unit}",
                                    raw=data,
                                )
                            )
                        except Exception:
                            logger.exception("Error in progress_callback")
                else:
                    done = max(0, min(100, int(round(100.0 - remaining))))
                    logger.debug(
                        f"Job {job_id}: Progress: {done}% (remaining: {remaining}%)"
                    )
                    if progress_callback is not None:
                        try:
                            progress_callback(
                                ProgressEvent(
                                    job_id=job_id,
                                    worker="",
                                    kind="remaining",
                                    done=done,
                                    total=100,
                                    raw=data,
                                )
                            )
                        except Exception:
                            logger.exception("Error in progress_callback")
            except Exception as e:
                logger.warning(
                    f"Could not interpret remaining value for job {job_id}: {data.get('remaining')} ({e})"
                )

        # Log any other message types we're not handling
        else:
            logger.debug(f"Received unhandled message type for job {job_id}: {data}")

    # Set up the listener
    logger.info(f"Setting up batch progress listener")
    listener = JobBatchProgressListener(job_ids, _on_message)
    connection.add_listener(listener)

    # Subscribe to topics for all jobs in the batch (one subscription per job).
    for job_id in job_ids:
        topic = f"/topic/{job_id}.*.*.progress"
        logger.debug(f"Subscribing to {topic}")
        connection.subscribe(destination=topic, id=f"{listener.uid}-{job_id}")

    if auto_start:
        # Start all jobs with updated statuses
        logger.info(f"Auto-starting {len(jobs)} jobs")
        for job_id in job_ids:
            logger.debug(f"Starting job {job_id}")
            result = api.update_job_status(job_id, JOB_STATUS["QueuedForMeshing"])
            job_statuses[job_id] = "QueuedForMeshing"
            logger.debug(f"Job {job_id} queued with result: {result}")

        update_status_counts()

    # Track completed jobs
    completed_jobs = set()
    timed_out = False
    final_statuses: Dict[str, str] = {}

    # Use tqdm batch bar only when no custom callback is provided.
    _use_tqdm = progress_callback is None

    try:
        pbar_ctx = (
            tqdm(total=len(jobs), desc=f"Monitoring {len(jobs)} jobs", leave=True)
            if _use_tqdm
            else None
        )
        with pbar_ctx if pbar_ctx is not None else _NullContext() as pbar:
            while len(completed_jobs) < len(jobs) and not timed_out:
                # Check for timeout
                elapsed_since_activity = loop.time() - last_activity

                # Check if listener has received any messages recently
                if listener.last_message_time is not None:
                    logger.debug(
                        f"Listener has received {listener.message_count} messages, last at {listener.last_message_time}"
                    )

                if elapsed_since_activity > message_timeout:
                    logger.warning(
                        f"No activity for {elapsed_since_activity:.1f}s, timeout exceeded ({message_timeout}s)"
                    )

                    # Additional debugging info
                    logger.warning("TIMEOUT DEBUG INFO:")
                    logger.warning(
                        f"- Listener message count: {listener.message_count}"
                    )
                    logger.warning(f"- Last message time: {listener.last_message_time}")
                    logger.warning(f"- Job statuses: {job_statuses}")

                    # Check connection health
                    if hasattr(connection, "is_connected") and callable(
                        connection.is_connected
                    ):
                        logger.warning(
                            f"- STOMP connection status: {connection.is_connected()}"
                        )

                    timed_out = True
                    break

                # Update display with status distribution (tqdm path only)
                if pbar is not None:
                    status_display = " | ".join(
                        [
                            f"{status}: {count}"
                            for status, count in status_counts.items()
                            if count > 0
                        ]
                    )
                    pbar.set_description(f"Jobs: {status_display}")

                # Check for newly completed jobs
                for job_id in job_ids:
                    if (
                        job_id not in completed_jobs
                        and job_status_events[job_id].is_set()
                    ):
                        logger.info(f"Job {job_id} completed, updating progress bar")
                        completed_jobs.add(job_id)
                        if pbar is not None:
                            pbar.update(1)  # Increment progress bar

                # Also check job status directly with the API periodically (every 5s)
                current_time = loop.time()
                if int(current_time) % 5 == 0:
                    logger.debug("Performing periodic API status check")
                    for job_id in job_ids:
                        if job_id not in completed_jobs:
                            try:
                                job_data = api.get_job(job_id)
                                status_val = job_data.get("status")
                                status_name = STATUS_JOB.get(status_val, "Unknown")
                                logger.debug(
                                    f"API check for job {job_id}: status={status_name}"
                                )

                                # Update tracked status
                                if job_statuses[job_id] != status_name:
                                    logger.info(
                                        f"Job {job_id} status changed to {status_name} (API check)"
                                    )
                                    job_statuses[job_id] = status_name
                                    update_status_counts()

                                    # Update last_activity since we got a status change
                                    last_activity = current_time

                                # Check if job is complete
                                if status_val >= JOB_STATUS["Complete"]:
                                    logger.info(
                                        f"Job {job_id} marked complete from API check"
                                    )
                                    job_status_events[job_id].set()
                            except Exception as e:
                                logger.warning(f"Failed to check job {job_id}: {e}")

                # Brief sleep to avoid CPU spinning
                await asyncio.sleep(0.5)

        logger.info(
            f"Monitoring complete: {len(completed_jobs)}/{len(jobs)} jobs finished"
        )

        # Get final status for all jobs
        for job_id in job_ids:
            try:
                logger.debug(f"Getting final status for job {job_id}")
                result = api.get_job(job_id)
                status_val = result.get("status")
                final_statuses[job_id] = STATUS_JOB.get(
                    status_val, f"Unknown ({status_val})"
                )
                logger.info(f"Final status for job {job_id}: {final_statuses[job_id]}")
            except Exception as e:
                logger.error(f"Failed to get final status for job {job_id}: {e}")
                final_statuses[job_id] = f"Error: {e}"

    finally:
        # Clean up subscriptions using the same IDs used when subscribing.
        logger.debug("Cleaning up subscriptions and listener")
        try:
            for job_id in job_ids:
                sub_id = f"{listener.uid}-{job_id}"
                logger.debug(f"Unsubscribing from ID {sub_id}")
                connection.unsubscribe(id=sub_id)
            connection.remove_listener(listener)
        except Exception as e:
            logger.debug(
                f"Failed to clean up listener/subscriptions: {e}", exc_info=True
            )

    # Return results including timeout info if applicable
    if timed_out:
        logger.warning("Job monitoring timed out after no activity")
        return {**final_statuses, "_monitoring_status": "TIMED_OUT"}

    logger.info(
        f"Batch monitoring complete, returning final statuses for {len(jobs)} jobs"
    )
    return final_statuses
