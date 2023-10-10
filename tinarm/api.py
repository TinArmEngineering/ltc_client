import logging
import requests

LOGGING_LEVEL = logging.INFO


### Configure Logging
logger = logging.getLogger()
logger.setLevel(LOGGING_LEVEL)


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

        logger.debug(f"node_id: {self._node_id}")
        logger.debug(f"root_url: {self._root_url}")
        


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
        url=f"{self._root_url}/jobs/{job_id}/status/{status}?nodeid={self._node_id}&apikey={self._api_key}"
        logger.debug(f"Updating job status: {url}")

        response = requests.put(url=url)
        return response.json()
    

    def get_job_artifact(self, job_id, artifact_id):
        """
        Get a job artifact
        """
        job = self.get_job(job_id)
        for artifact in job["artifacts"]:
            if artifact["id"] == artifact_id:
                return artifact
    

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
            job_id, 
            type, 
            f"file://{self._node_id}/{filename}", 
            promote)
    
    
    def update_job_artifact(self, job_id, artifact_id, artifact):
        """
        Update an artifact
        """
        response = requests.put(
            url=f"{self._root_url}/jobs/{job_id}/artifacts/{artifact_id}?apikey={self._api_key}",
            json=artifact
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
