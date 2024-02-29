import logging
import time
import requests

LOGGING_LEVEL = logging.INFO

JOB_STATUS = {
    "New": 0,
    "QueuedForMeshing": 10,
    "Meshing": 20,
    "QueuedForMeshConversion": 25,
    "MeshConversion": 26,
    "QueuedForSolving": 30,
    "Solving": 40,
    "QueuedForPostProcess": 50,
    "PostProcess": 60,
    "Complete": 70,
    "Quarantined": 80,
}


### Configure Logging
logger = logging.getLogger()
logger.setLevel(LOGGING_LEVEL)


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
    def __init__(self, magnitude, shape, units: list[Unit]):
        self.magnitude = magnitude
        self.shape = shape

        # I'm very happy with this line of code
        self.units = [Unit(*u) if type(u) != Unit else u for u in units]

    def to_dict(self):
        return {"magnitude": self.magnitude, "units": [u.to_dict() for u in self.units]}


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

    def __init__(self, node_id, root_url, api_key):
        """
        Initialize the API
        """

        self._node_id = node_id
        self._root_url = root_url
        self._api_key = api_key

        logger.info(f"node_id: {self._node_id}")
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

    def update_job_status(self, job_id, status):
        """
        Update a job status
        """
        url = f"{self._root_url}/jobs/{job_id}/status/{status}?node_id={self._node_id}&apikey={self._api_key}"
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
            job_id, type, f"file://{self._node_id}/{filename}", promote
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

    def delete_job(self, job_id, hard=False):
        """
        Delete a job
        """
        response = requests.delete(
            url=f"{self._root_url}/jobs/{job_id}?hard={hard}&apikey={self._api_key}",
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
