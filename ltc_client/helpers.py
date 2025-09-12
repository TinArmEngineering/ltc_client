from .api import Quantity, NameQuantityPair
from .api import JOB_STATUS, STATUS_JOB

import random
import requests
import pint
from webstompy import StompListener
from tqdm.auto import tqdm
import numpy as np
import logging
import uuid
import asyncio
import json
from uuid import uuid4
from typing import Any, Tuple


logger = logging.getLogger(__name__)

q = pint.get_application_registry()


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

    units_tuple: Tuple[Tuple[str, int], ...] = tuple(
        (e["name"], e["exponent"]) for e in enc.get("units", ())
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
        quant.ito_base_units()
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


class TqdmUpTo(tqdm):
    """Provides `update_to(n)` which uses `tqdm.update(delta_n)`."""

    def update_to(self, b=1, bsize=1, tsize=None):
        """
        b  : int, optional
            Number of blocks transferred so far [default: 1].
        bsize  : int, optional
            Size of each block (in tqdm units) [default: 1].
        tsize  : int, optional
            Total size (in tqdm units). If [default: None] remains unchanged.
        """
        if tsize is not None:
            self.total = tsize
        return self.update(b * bsize - self.n)  # also sets self.n = b * bsize


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

            # TODO specify progress messages in a scheme. some progress payloads use 'done' / 'total'
            if isinstance(data, dict):
                if "done" in data:
                    logger.debug(
                        "Progress update: done=%s, total=%s",
                        data["done"],
                        data.get("total"),
                    )
                    self._callback_fn(
                        data["done"],
                        tsize=data.get("total"),
                        worker=worker_name,
                        message_type="progress",
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
                        status_val,
                        tsize=None,
                        worker=worker_name,
                        message_type="status",
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
                                None,
                                tsize=None,
                                worker=worker_name,
                                message_type="time_remaining",
                                remaining_time=f"{remaining:.1f} {unit}",
                            )
                        else:
                            done = max(0, min(100, int(round(100.0 - remaining))))
                            logger.debug(
                                "Remaining percent update: remaining=%s, done=%s",
                                remaining,
                                done,
                            )
                            self._callback_fn(
                                done,
                                tsize=100,
                                worker=worker_name,
                                message_type="remaining",
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


async def async_job_monitor(api, my_job, connection, position, auto_start=True):
    uid = str(uuid4())
    listener = ProgressListener(my_job, uid)
    connection.add_listener(listener)
    connection.subscribe(destination=f"/topic/{my_job.id}.*.*.progress", id=uid)

    done_event = asyncio.Event()

    # capture the running loop so listener (which may run in another thread)
    # can schedule callbacks safely on the asyncio loop.
    loop = asyncio.get_running_loop()

    with TqdmUpTo(
        total=100,
        desc=f"Job {my_job.title}",
        position=position,
        leave=False,
    ) as pbar:
        # handle updates on the asyncio loop thread
        def _on_progress(done, tsize=None, worker=None, message_type=None, **kw):
            try:
                # numeric progress -> update bar
                if isinstance(done, (int, float)):
                    pbar.n = max(pbar.n, int(done))
                    pbar.refresh()
                # status messages: mark done when threshold reached
                if message_type == "status" or isinstance(done, int):
                    try:
                        status_val = int(done)
                        if status_val >= JOB_STATUS["Complete"]:
                            done_event.set()
                    except Exception:
                        pass
            except Exception:
                logger.exception("Error in _on_progress handler")

        # wrapper invoked by ProgressListener (likely not on loop thread)
        def _cb_wrapper(*args, **kwargs):
            import functools

            try:
                # schedule actual handling on asyncio loop thread (bind kwargs via partial)
                loop.call_soon_threadsafe(
                    functools.partial(_on_progress, *args, **kwargs)
                )
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
    from .material import Material  # type: ignore
    from .job import Job  # type: ignore
except Exception:
    logger.exception("Deferred import of Material/Job failed")
    raise
