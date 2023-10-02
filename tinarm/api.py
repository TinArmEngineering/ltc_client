import requests


class TaeApi:
    """
    The TAE API
    """

    def __init__(self, root_url, api_key):
        self.root_url = root_url
        self.api_key = api_key

    def get_job(self, job_id):
        """
        Get a job from the TAE API
        """
        response = requests.get(
            url=f"{self.root_url}/jobs/{job_id}?apikey={self.api_key}",
        )
        return response.json()
    
    def post_job_artifact(self, job_id):
        """
        Post an artifact to a job
        """
        response = requests.post(
            url=f"{self.root_url}/jobs/{job_id}/artifacts?apikey={self.api_key}",
            json={
                "type": "test",
                "url": "monster+file://lala/looloo/test.txt",
            },
        )
        return response.json()

