import os
import sys
import mock
import unittest
from teamcity import is_running_under_teamcity
from teamcity.unittestpy import TeamcityTestRunner

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import tinarm

NODE_ID = "testnode"
ROOT_URL = "http://example.com"
API_KEY = "1234"
JOB_ID = "4568"
JOB_STATUS = 20
JOB_ARTIFACT_ID = "6544"
JOB_ARTIFACT_TYPE = "TEST_PLOT"
JOB_ARTIFACT_FILE_PATH = "/lala/test_plot.png"
JOB_ARTIFACT_FILE_URL = "file://testnode/" + JOB_ARTIFACT_FILE_PATH
JOB_ARTIFACT_REMOTE_URL = "https://example.com/test_plot.png"

api = tinarm.Api(NODE_ID, ROOT_URL, API_KEY)

class ApiTestCase(unittest.TestCase):

    @mock.patch("tinarm.api.requests")
    def test_get_job(self, mock_requests):
        api.get_job(JOB_ID)
        mock_requests.get.assert_called_with(
            url=f"{ROOT_URL}/jobs/{JOB_ID}?apikey={API_KEY}",
        )

    @mock.patch("tinarm.api.requests")
    def test_update_job_status(self, mock_requests):
        api.update_job_status(JOB_ID, JOB_STATUS)
        mock_requests.put.assert_called_with(
            url=f"{ROOT_URL}/jobs/{JOB_ID}/status/{JOB_STATUS}?nodeid={NODE_ID}&apikey={API_KEY}"
        )

    @mock.patch("tinarm.api.requests")
    def test_get_job_artifact_not_found(self, mock_requests):
        with self.assertRaises(Exception):
            api.get_job_artifact(JOB_ID, JOB_ARTIFACT_ID)
        mock_requests.get.assert_called_with(
            url=f"{ROOT_URL}/jobs/{JOB_ID}?apikey={API_KEY}",
        )

    @mock.patch("tinarm.api.requests")
    def test_get_promoted_job_artifact_raise(self, mock_requests):
        with self.assertRaises(Exception):
            api.get_promoted_job_artifact('12', '34')
        mock_requests.get.assert_called_with(
            url=f"{ROOT_URL}/jobs/12?apikey={API_KEY}",
        )

    @mock.patch("tinarm.api.requests")
    def test_get_promoted_job_artifact(self, mock_requests):

        mock_requests.get.return_value.json.return_value = {
            "artifacts": [ {
                    "id": JOB_ARTIFACT_ID,
                    "url": JOB_ARTIFACT_REMOTE_URL,
                }
            ]
        }

        # Call get_promoted_job_artifact fassing a callback function
        api.get_promoted_job_artifact(JOB_ID, JOB_ARTIFACT_ID)

        mock_requests.get.assert_called_with(
            url=f"{ROOT_URL}/jobs/{JOB_ID}?apikey={API_KEY}",
        )
        

    @mock.patch("tinarm.api.requests")
    def test_create_job_artifact(self, mock_requests):
        api.create_job_artifact(JOB_ID, JOB_ARTIFACT_TYPE, JOB_ARTIFACT_REMOTE_URL)
        mock_requests.post.assert_called_with(
            url=f"{ROOT_URL}/jobs/{JOB_ID}/artifacts?promote=False&apikey={API_KEY}",
            json={
                "type": JOB_ARTIFACT_TYPE,
                "url": JOB_ARTIFACT_REMOTE_URL,
            },
        )

    @mock.patch("tinarm.api.requests")
    def test_create_job_artifact_from_file(self, mock_requests):
        api.create_job_artifact_from_file(JOB_ID, JOB_ARTIFACT_TYPE, JOB_ARTIFACT_FILE_PATH)
        mock_requests.post.assert_called_with(
            url=f"{ROOT_URL}/jobs/{JOB_ID}/artifacts?promote=False&apikey={API_KEY}",
            json={
                "type": JOB_ARTIFACT_TYPE,
                "url": JOB_ARTIFACT_FILE_URL,
            },
        )

    @mock.patch("tinarm.api.requests")
    def test_update_job_artifact(self, mock_requests):
        api.create_job_artifact_from_file(JOB_ID, JOB_ARTIFACT_TYPE, JOB_ARTIFACT_FILE_PATH, True)
        mock_requests.post.assert_called_with(
            url=f"{ROOT_URL}/jobs/{JOB_ID}/artifacts?promote=True&apikey={API_KEY}",
            json={
                "type": JOB_ARTIFACT_TYPE,
                "url": JOB_ARTIFACT_FILE_URL,
            },
        )

    @mock.patch("tinarm.api.requests")
    def test_update_job_artifact(self, mock_requests):
        api.update_job_artifact(JOB_ID, JOB_ARTIFACT_ID, {"type": JOB_ARTIFACT_TYPE, "url": JOB_ARTIFACT_REMOTE_URL} )
        mock_requests.put.assert_called_with(
            url=f"{ROOT_URL}/jobs/{JOB_ID}/artifacts/{JOB_ARTIFACT_ID}?apikey={API_KEY}",
            json={
                "type": JOB_ARTIFACT_TYPE,
                "url": JOB_ARTIFACT_REMOTE_URL,
            },
        )

    @mock.patch("tinarm.api.requests")
    def test_promote_job_artifact(self, mock_requests):
        api.promote_job_artifact(JOB_ID, JOB_ARTIFACT_ID)
        mock_requests.put.assert_called_with(
            url=f"{ROOT_URL}/jobs/{JOB_ID}/artifacts/{JOB_ARTIFACT_ID}/promote?apikey={API_KEY}",
        )


    
if __name__ == "__main__":
    if is_running_under_teamcity():
        runner = TeamcityTestRunner()
    else:
        runner = unittest.TextTestRunner()
    unittest.main(testRunner=runner)