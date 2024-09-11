from . import Quantity, NameQuantityPair
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

logger = logging.getLogger(__name__)

q = pint.get_application_registry()


def decode(enc):
    """Decode a quantity encoded object

    Parameters
    ----------
    enc : dict
        The encoded object

    Returns
    -------
    Quantity
        The decoded quantity object

    """
    if len(enc["magnitude"]) != 1:
        enc_tuple = tuple(
            (
                np.array(enc["magnitude"], dtype=np.float64).reshape(enc["shape"]),
                tuple((e["name"], e["exponent"]) for e in enc.get("units", ())),
            )
        )
    else:
        enc_tuple = (
            enc["magnitude"][0],
            tuple((e["name"], e["exponent"]) for e in enc.get("units", ())),
        )
    try:
        quant = q.Quantity.from_tuple(enc_tuple)
        quant.ito_base_units()
    except:
        logger.error(
            "Error decoding {0}".format(
                (
                    enc["magnitude"],
                    ((e["name"], e["exponent"]) for e in enc.get("units", ())),
                )
            )
        )
        raise

    logger.debug("convert {i} -> {o:~P}".format(o=quant, i=enc))
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


class Job(object):
    def __init__(self, machine: Machine, operating_point, simulation, title=None):
        if title is None:
            self.title = self.generate_title()
        else:
            self.title = title
        self.type = "electromagnetic_spmbrl_fscwseg"
        self.status = 0
        self.machine = machine
        self.operating_point = operating_point
        self.simulation = simulation

    def __repr__(self) -> str:
        return f"Job({self.machine}, {self.operating_point}, {self.simulation})"

    def generate_title(self):
        "gets a random title from the wordlists"
        random_offset = random.randint(500, 286797)
        response = requests.get(
            "https://github.com/taikuukaits/SimpleWordlists/raw/master/Wordlist-Adjectives-All.txt",
            headers={
                "Range": "bytes={1}-{0}".format(random_offset, random_offset - 500),
                "accept-encoding": "identity",
            },
        )
        adjective = random.choice(response.text.splitlines()[1:-1])
        random_offset = random.randint(500, 871742)
        response = requests.get(
            "https://github.com/taikuukaits/SimpleWordlists/raw/master/Wordlist-Nouns-All.txt",
            headers={
                "Range": "bytes={1}-{0}".format(random_offset, random_offset - 500),
                "accept-encoding": "identity",
            },
        )
        noun = random.choice(response.text.splitlines()[1:-1])
        title = f"{adjective}-{noun}"
        return title

    def to_api(self):
        job = {
            "status": 0,
            "title": self.title,
            "type": self.type,
            "tasks": 11,
            "data": [],
            "materials": [],
        }

        operating_point_api = [
            NameQuantityPair(
                "operating_point", k, Quantity(*self.operating_point[k].to_tuple())
            )
            for k in self.operating_point
        ]

        simulation_api = [
            NameQuantityPair("simulation", k, Quantity(*self.simulation[k].to_tuple()))
            for k in self.simulation
        ]

        job["data"].extend(list(x.to_dict() for x in operating_point_api))
        job["data"].extend(list(x.to_dict() for x in simulation_api))
        job["data"].extend(self.machine.to_api())
        job["materials"] = [
            {"part": key, "material_id": value}
            for key, value in self.machine.materials.items()
        ]
        return job

    def run(self):
        pass


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
        self.done = False
        self._callback_fn = None  # Initialize the callback function

    @property
    def callback_fn(self):
        return self._callback_fn

    @callback_fn.setter
    def callback_fn(self, fn):
        self._callback_fn = fn

    def on_message(self, frame):
        headers = {key.decode(): value.decode() for key, value in frame.header}
        if headers["subscription"] == self.uid:
            try:
                time_str, level_str, mesg_str = frame.message.decode().split(" - ")
            except ValueError:
                logger.warning("Unable to process", frame)
            else:
                data = json.loads(mesg_str.strip())
                if "done" in data:
                    self.callback_fn(data["done"], tsize=data["total"])
                    if data["done"] == data["total"]:
                        self.done = True
                        return self.done
        else:
            return


async def async_job_monitor(api, my_job, connection, position):
    """
    Monitor the progress of a job and update the progress bar

    Parameters
    ----------
    api : ltc_client.api.API
        The API object
    my_job : ltc_client.helpers.Job
        The job object
    connection : webstompy.StompConnection
        The connection object
    position : int
        The position of the progress bar

    Returns
    -------
    int
        The status of the job


    """
    uid = str(uuid.uuid4())
    listener = ProgressListener(my_job, uid)
    connection.add_listener(listener)
    connection.subscribe(destination=f"/topic/{my_job.id}.solver.*.progress", id=uid)
    with TqdmUpTo(
        total=my_job.simulation["timestep_intervals"],
        desc=f"Job {my_job.title}",
        position=position,
        leave=False,
    ) as pbar:
        listener.callback_fn = pbar.update_to

        j1_result = api.update_job_status(my_job.id, JOB_STATUS["QueuedForMeshing"])

        while not listener.done:
            await asyncio.sleep(1)  # sleep for a second
        return STATUS_JOB[api.get_job(my_job.id)["status"]]
