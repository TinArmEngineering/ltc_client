import logging
import time
import requests
from math import prod
import pint

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .helpers import Material

LOGGING_LEVEL = logging.INFO

JOB_STATUS = {
    "New": 0,
    "QueuedForMeshing": 10,
    "WaitingForMesh": 20,
    "QueuedForSimSetup": 21,
    "SimSetup": 22,
    "QueuedForMeshConversion": 25,
    "MeshConversion": 26,
    "QueuedForSolving": 30,
    "Solving": 40,
    "QueuedForPostProcess": 50,
    "PostProcess": 60,
    "Complete": 70,
    "Quarantined": 80,
}

LOG_LEVEL = {
    "Fatal": 0,
    "Error": 1,
    "Warning": 2,
    "Info": 3,
    "Debug": 4,
    "Trace": 5,
}

# Invert the JOB_STATUS dictionary
STATUS_JOB = {value: key for key, value in JOB_STATUS.items()}

### Configure Logging
logger = logging.getLogger()
logger.setLevel(LOGGING_LEVEL)


class Log(object):

    def __init__(
        self, associated_job_id, level: int, service, code, message, call_stack
    ):

        self.associated_job_id = associated_job_id
        self.level = level
        self.service = service
        self.node = None
        self.code = code
        self.message = message
        self.call_stack = call_stack

    def to_api(self):

        return {
            "associated_job_id": self.associated_job_id,
            "level": self.level,
            "service": self.service,
            "node": self.node,
            "code": self.code,
            "message": self.message,
            "call_stack": self.call_stack,
        }


class Unit:
    def __init__(self, name: str, exponent: int):
        self.name = name
        self.exponent = exponent

    def to_dict(self):
        return {
            "name": self.name,
            "exponent": self.exponent,
        }


class Quantity:
    """
    Represents a quantity with magnitude, units, and shape.

    Args:
        magnitude: The magnitude of the quantity. It can be a single value, a list-like object, or a numpy array.
        or even a pint.Quantity
        units (list[Unit]): A list of Unit objects representing the units of the quantity.
        shape (Optional): The shape of the quantity. If not provided, it will be inferred from the magnitude.

    Attributes:
        magnitude: The magnitude of the quantity.
        shape: The shape of the quantity.
        units (list[Unit]): A list of Unit objects representing the units of the quantity.
    """

    def __init__(self, magnitude, units=[None], shape=None):
        if isinstance(magnitude, pint.Quantity):
            magnitude, units = magnitude.to_tuple()
        if hasattr(magnitude, "shape"):
            if shape is None:
                self.shape = list(magnitude.shape)
                self.magnitude = magnitude.flatten().tolist()
            elif prod(shape) == magnitude.size:
                self.magnitude = magnitude.tolist()
                self.shape = shape
            else:
                raise ValueError(
                    f"Shape {shape} does not match magnitude size {magnitude.size}"
                )

        elif not hasattr(magnitude, "__len__"):
            self.magnitude = [magnitude]
            self.shape = [1]
        elif shape is None:
            self.shape = [len(magnitude)]
            self.magnitude = magnitude
        elif prod(shape) != len(magnitude):
            raise ValueError(
                f"Shape {shape} does not match magnitude size {len(magnitude)}"
            )
        else:
            self.magnitude = magnitude
            self.shape = shape

        self.units = [Unit(*u) if type(u) != Unit else u for u in units]

    def to_dict(self):
        """
        Converts the Quantity object to a dictionary.

        Returns:
            dict: A dictionary representation of the Quantity object.
        """
        return {
            "magnitude": self.magnitude,
            "shape": self.shape,
            "units": [u.to_dict() for u in self.units],
        }


class NameQuantityPair:
    def __init__(self, section, name, value: Quantity):
        self.section = section
        self.name = name
        self.value = value

    def to_dict(self):
        return {
            "section": self.section,
            "name": self.name,
            "value": self.value.to_dict(),
        }


class Api:
    """
    The TAE API
    """

    def __init__(self, root_url, api_key, org_id=None, node_id=None):
        """
        Initialize the API
        """

        self._root_url = root_url
        self._api_key = api_key
        self._org_id = org_id
        self._node_id = node_id

        logger.info(f"root_url: {self._root_url}")

    def get_job(self, job_id):
        """
        Get a job from the TAE API
        """
        response = requests.get(
            url=f"{self._root_url}/jobs/{job_id}?apikey={self._api_key}",
        )
        response.raise_for_status()
        return response.json()

    def create_job(self, job):
        """
        Create a job for the TAE API
        """
        response = requests.post(
            url=f"{self._root_url}/jobs/?apikey={self._api_key}&org_id={self._org_id}",
            json=job.to_api(),
        )
        response.raise_for_status()
        if response.status_code == 200:
            job.id = response.json()["id"]
        return response.json()

    def update_job_status(self, job_id, status, percentage_complete=None):
        """
        Update a job status
        """
        url = f"{self._root_url}/jobs/{job_id}/status/{status}?node_id={self._node_id}&apikey={self._api_key}&percentage_complete={percentage_complete}"
        logger.info(f"Updating job status: {url}")

        response = requests.put(url=url)
        response.raise_for_status()
        return response.json()

    def get_job_artifact(self, job_id, artifact_id):
        """
        Get job artifact
        """
        job = self.get_job(job_id)
        for artifact in job["artifacts"]:
            if artifact["id"] == artifact_id:
                return artifact

        raise Exception(f"Artifact {artifact_id} not found on job {job_id}")

    def get_promoted_job_artifact(self, job_id, artifact_id):
        # Get the artifact
        artifact = self.get_job_artifact(job_id, artifact_id)

        # If the url starts with https, it's already promoted
        if artifact["url"].startswith("https"):
            return artifact

        for i in range(0, 10):
            time.sleep(5)
            artifact = self.get_job_artifact(job_id, artifact_id)
            if artifact["url"].startswith("https"):
                return artifact

        raise Exception(
            f"Artifact {artifact_id} on job {job_id} could not be promoted in a reasonable time"
        )

    def create_job_artifact(self, job_id, type, url, promote=False):
        """
        Post an artifact to a job
        """
        response = requests.post(
            url=f"{self._root_url}/jobs/{job_id}/artifacts?promote={promote}&apikey={self._api_key}",
            json={
                "created_on_node": self._node_id,
                "type": type,
                "url": url,
            },
        )
        response.raise_for_status()
        return response.json()

    def create_job_artifact_from_file(self, job_id, type, filename, promote=False):
        """
        Post an artifact to a job
        """
        return self.create_job_artifact(
            job_id, type, f"file://{self._node_id}{filename}", promote
        )

    def update_job_artifact(self, job_id, artifact_id, artifact):
        """
        Update an artifact
        """
        response = requests.put(
            url=f"{self._root_url}/jobs/{job_id}/artifacts/{artifact_id}?apikey={self._api_key}",
            json=artifact,
        )
        response.raise_for_status()
        return response.json()

    def promote_job_artifact(self, job_id, artifact_id):
        """
        Promote an artifact to a job
        """
        response = requests.put(
            url=f"{self._root_url}/jobs/{job_id}/artifacts/{artifact_id}/promote?apikey={self._api_key}",
        )
        response.raise_for_status()
        return response.json()

    def delete_job(self, job_id):
        """
        Delete a job
        """
        response = requests.delete(
            url=f"{self._root_url}/jobs/{job_id}?apikey={self._api_key}",
        )
        response.raise_for_status()
        return

    def create_job_data(self, job_id: str, data: NameQuantityPair):
        """
        Create job data
        """
        response = requests.post(
            url=f"{self._root_url}/jobs/{job_id}/data?apikey={self._api_key}",
            json=data.to_dict(),
        )
        response.raise_for_status()
        return response.json()

    def update_job_data(self, job_id: str, data_name: str, data: NameQuantityPair):
        """
        Update job data
        """
        response = requests.put(
            url=f"{self._root_url}/jobs/{job_id}/data/{data_name}?apikey={self._api_key}",
            json=data.to_dict(),
        )
        response.raise_for_status()
        return response.json()

    def delete_job_data(self, job_id: str, data_name: str):
        """
        Delete job data
        """
        response = requests.delete(
            url=f"{self._root_url}/jobs/{job_id}/data/{data_name}?apikey={self._api_key}",
        )
        response.raise_for_status()

    def get_reusable_artifact(self, hash):
        """
        Get a reusable artifact from the TAE API
        """
        response = requests.get(
            url=f"{self._root_url}/reusable_artifacts/{hash}?apikey={self._api_key}",
        )
        response.raise_for_status()
        return response.json()

    def update_reusable_artifact(self, hash, reusable_artifact):
        """
        Update a reusable_artifact
        """
        response = requests.put(
            url=f"{self._root_url}/reusable_artifacts/{hash}?apikey={self._api_key}",
            json=reusable_artifact,
        )
        response.raise_for_status()
        return response.json()

    def update_reusable_artifact_url(self, hash, url, mimetype=None):
        """
        Update an reusable_artifact's URL
        """
        response = requests.patch(
            url=f"{self._root_url}/reusable_artifacts/{hash}/url?apikey={self._api_key}",
            json={"url": url, "mimetype": mimetype},
        )
        response.raise_for_status()
        return response.json()

    def create_reusable_artifact_data(self, hash, data: NameQuantityPair):
        """
        Create reusable_artifact data
        """
        response = requests.post(
            url=f"{self._root_url}/reusable_artifacts/{hash}/data?apikey={self._api_key}",
            json=data.to_dict(),
        )
        response.raise_for_status()
        return response.json()

    def promote_reusable_artifact(self, hash):
        """
        Promote reusable artifact
        """
        response = requests.put(
            url=f"{self._root_url}/reusable_artifacts/{hash}/promote?apikey={self._api_key}",
        )
        response.raise_for_status()
        return response.json()

    def get_material(self, material_id) -> "Material":
        """
        Get a material from the TAE API
        """
        from .helpers import Material

        response = requests.get(
            url=f"{self._root_url}/materials/{material_id}?apikey={self._api_key}",
        )
        response.raise_for_status()
        return Material.from_api(response.json())

    def create_material(self, material: "Material"):
        """
        Create a material for the TAE API
        """
        response = requests.post(
            url=f"{self._root_url}/materials?apikey={self._api_key}",
            json=material.to_api(),
        )
        response.raise_for_status()
        if response.status_code == 200:
            material.material_id = response.json()["id"]
        return response.json()

    def get_jobs(self):
        """
        Get all jobs
        """
        response = requests.get(
            url=f"{self._root_url}/jobs?apikey={self._api_key}",
        )
        response.raise_for_status()
        return response.json()

    def create_log(self, log: Log):
        """
        Create a server log
        """

        log.node = self._node_id

        response = requests.post(
            url=f"{self._root_url}/logs?apikey={self._api_key}",
            json=log.to_api(),
        )
        response.raise_for_status()
        return response.json()
