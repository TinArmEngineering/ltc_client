import requests

from pbmodel import file_pb2

class Api:
    """
    The TAE API
    """

    def __init__(self, node_id, root_url, api_key):
        self._node_id = node_id
        self._root_url = root_url
        self._api_key = api_key


    def get_job(self, job_id):
        """
        Get a job from the TAE API
        """
        response = requests.get(
            url=f"{self._root_url}/jobs/{job_id}?apikey={self._api_key}",
        )
        return response.json()
    

    def update_job_status(self, job_id, status):
        """
        Update a job status
        """
        response = requests.put(
            url=f"{self._root_url}/jobs/{job_id}/status/{status}?apikey={self._api_key}"
        )
        return response.json()
    

    def get_job_artifact(self, job_id, artifact_id):
        """
        Get a job artifact
        """
        job = self.get_job(job_id)
        for artifact in job["artifacts"]:
            if artifact["id"] == artifact_id:
                return artifact
    

    def create_job_artifact(self, job_id, type, filename, immediate_promote=False):
        """
        Post an artifact to a job
        """
        url=f"{self._root_url}/jobs/{job_id}artifacts?apikey={self._api_key}",

        if immediate_promote:
            testFilePb = _get_file_protobuf(filename, type)

            response = requests.post(
                url=url,
                data=testFilePb.SerializeToString(),
                headers={"Content-Type": "application/x-protobuf"},
            )

            # Read the raw response body
            respPb = file_pb2.CreateFileResponse()
            respPb.ParseFromString(response.content)

            return respPb.id
        else:
            response = requests.post(
                url=url,
                json={
                    "type": type,
                    "url": f"file://{self._node_id}/{filename}",
                },
            )
            return response.json()["id"]
        

    def promote_job_artifact(self, job_id, artifact_id):
        """
        Promote an artifact to a job
        """
        response = requests.put(
            url=f"{self._root_url}/jobs/{job_id}/artifacts/{artifact_id}/promote?apikey={self._api_key}",
        )
        return response.json()
    


def _read_file(filename, mode):
    with open(filename, mode) as f:
        return f.read()


def _get_file_protobuf(filename, filetype):
    # read the contents of test_file.txt into a string
    fileContent = _read_file(filename, "rb")

    # Create a protobuf object
    filePbuf = file_pb2.CreateFileRequest()
    filePbuf.name = filename
    filePbuf.content = fileContent
    filePbuf.type = filetype
    filePbuf.description = filetype

    return filePbuf
    
