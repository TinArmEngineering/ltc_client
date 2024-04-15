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
ORG_ID = "9ABC"
JOB_STATUS = 20
JOB_ARTIFACT_ID = "6544"
JOB_ARTIFACT_TYPE = "TEST_PLOT"
JOB_ARTIFACT_FILE_PATH = "/lala/test_plot.png"
JOB_ARTIFACT_FILE_URL = "file://testnode" + JOB_ARTIFACT_FILE_PATH
JOB_ARTIFACT_REMOTE_URL = "https://example.com/test_plot.png"


api = tinarm.Api(root_url=ROOT_URL, api_key=API_KEY, org_id=ORG_ID, node_id=NODE_ID)


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
            url=f"{ROOT_URL}/jobs/{JOB_ID}/status/{JOB_STATUS}?node_id={NODE_ID}&apikey={API_KEY}&percentage_complete=None"
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
            api.get_promoted_job_artifact("12", "34")
        mock_requests.get.assert_called_with(
            url=f"{ROOT_URL}/jobs/12?apikey={API_KEY}",
        )

    @mock.patch("tinarm.api.requests")
    def test_get_promoted_job_artifact(self, mock_requests):
        mock_requests.get.return_value.json.return_value = {
            "artifacts": [
                {
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
                "created_on_node": NODE_ID,
                "type": JOB_ARTIFACT_TYPE,
                "url": JOB_ARTIFACT_REMOTE_URL,
            },
        )

    @mock.patch("tinarm.api.requests")
    def test_create_job_artifact_from_file(self, mock_requests):
        api.create_job_artifact_from_file(
            JOB_ID, JOB_ARTIFACT_TYPE, JOB_ARTIFACT_FILE_PATH
        )
        mock_requests.post.assert_called_with(
            url=f"{ROOT_URL}/jobs/{JOB_ID}/artifacts?promote=False&apikey={API_KEY}",
            json={
                "created_on_node": NODE_ID,
                "type": JOB_ARTIFACT_TYPE,
                "url": JOB_ARTIFACT_FILE_URL,
            },
        )

    @mock.patch("tinarm.api.requests")
    def test_update_job_artifact(self, mock_requests):
        api.create_job_artifact_from_file(
            JOB_ID, JOB_ARTIFACT_TYPE, JOB_ARTIFACT_FILE_PATH, True
        )
        mock_requests.post.assert_called_with(
            url=f"{ROOT_URL}/jobs/{JOB_ID}/artifacts?promote=True&apikey={API_KEY}",
            json={
                "type": JOB_ARTIFACT_TYPE,
                "url": JOB_ARTIFACT_FILE_URL,
            },
        )

    @mock.patch("tinarm.api.requests")
    def test_update_job_artifact(self, mock_requests):
        api.update_job_artifact(
            JOB_ID,
            JOB_ARTIFACT_ID,
            {"type": JOB_ARTIFACT_TYPE, "url": JOB_ARTIFACT_REMOTE_URL},
        )
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

    def test_tae_model(self):
        jobdata = tinarm.NameQuantityPair(
            "section",
            "name",
            tinarm.Quantity(
                magnitude=[4242],
                units=[tinarm.Unit("millimeter", 2), tinarm.Unit("second", -1)],
                shape=[1],
            ),
        )

        asDict = jobdata.to_dict()
        self.assertEqual(asDict["section"], "section")
        self.assertEqual(asDict["name"], "name")

    def test_Quantity_from_pint_value(self):
        import pint

        inval = pint.Quantity(42, "millimeter")
        outval = tinarm.Quantity(inval).to_dict()
        self.assertEqual(outval["magnitude"], [42])
        self.assertEqual(outval["units"], [tinarm.Unit("millimeter", 2)])

    def test_Qauntity_from_mulitdim_pint_value(self):
        import numpy as np
        import pint

        inval = np.ones((2, 2, 2)) * pint.Quantity(1.0, "tesla")
        outval = tinarm.Quantity(inval).to_dict()
        self.assertAlmostEqual(
            outval["magnitude"], [1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0]
        )
        self.assertEqual(outval["shape"], [2, 2, 2])
        self.assertEqual(outval["units"], [{"name": "tesla", "exponent": 1}])

    def test_Quantity_from_single_value(self):
        outval = tinarm.Quantity(42, [tinarm.Unit("millimeter", 2)]).to_dict()
        self.assertEqual(outval["magnitude"], [42])
        self.assertEqual(outval["shape"], [1])

    def test_Quantity_from_numpy_array(self):
        import numpy as np

        start = np.ones((2, 2, 3))
        outval = tinarm.Quantity(start, [tinarm.Unit("millimeter", 2)]).to_dict()
        self.assertEqual(outval["magnitude"], start.flatten().tolist())
        self.assertEqual(tuple(outval["shape"]), [2, 2, 3])

    def test_Quantity_from_list(self):
        outval = tinarm.Quantity([42, 43], [tinarm.Unit("millimeter", 2)]).to_dict()
        self.assertEqual(outval["magnitude"], [42, 43])
        self.assertEqual(outval["shape"], [2])

    def test_Quantity_with_invalid_shape(self):
        with self.assertRaises(ValueError):
            tinarm.Quantity([42, 43], [tinarm.Unit("millimeter", 2)], [2, 2])

    def test_tae_model_from_pint(self):
        """
        Test case for the `tae_model_from_pint` method.

        This test case verifies the behavior of the `tae_model_from_pint` method by creating a random array of quantities
        using the `pint` library and converting it to a `NameQuantityPair` object. It then checks if the converted object's
        attributes match the expected values.

        """
        import numpy as np
        import pint

        q = pint.UnitRegistry()
        indat = np.random.rand(2, 5, 3) * q.meter
        value, units = indat.to_tuple()
        jobdata = tinarm.NameQuantityPair(
            "section",
            "name",
            tinarm.Quantity(tuple(value.flatten()), units, indat.shape),
        )

        asDict = jobdata.to_dict()
        self.assertEqual(asDict["section"], "section")
        self.assertEqual(asDict["name"], "name")

    def test_decode(self):
        import pint

        q = pint.UnitRegistry()

        in_quant = {
            "magnitude": [42, 43],
            "shape": [2],
            "units": [{"name": "millimeter", "exponent": 2}],
        }
        out_quant = tinarm.decode(in_quant)
        self.assertTrue((out_quant.to(q.mm**2).magnitude == [42, 43]).all())
        self.assertEqual(out_quant.shape, [2])
        self.assertEqual(out_quant.dimensionality, q.UnitsContainer({"[length]": 2.0}))


if __name__ == "__main__":
    if is_running_under_teamcity():
        runner = TeamcityTestRunner()
    else:
        runner = unittest.TextTestRunner()
    unittest.main(testRunner=runner)
