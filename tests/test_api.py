import os
import sys
import mock
import unittest
import pint

from teamcity import is_running_under_teamcity
from teamcity.unittestpy import TeamcityTestRunner

import ltc_client
from ltc_client import Api, NameQuantityPair, Quantity, Unit, Log, Material, decode

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
MATERIAL_ID = "66018e5d1cd3bd0d3453646f"
Q = pint.get_application_registry()

api = ltc_client.Api(root_url=ROOT_URL, api_key=API_KEY, org_id=ORG_ID, node_id=NODE_ID)


class ApiTestCase(unittest.TestCase):
    @mock.patch("ltc_client.api.requests")
    def test_create_log(self, mock_requests):
        message = ltc_client.Log(
            associated_job_id=JOB_ID,
            level="info",
            service="test",
            code="test",
            message="test message",
            call_stack="test callstack",
        )

        api.create_log(message)
        mock_requests.post.assert_called_with(
            url=f"{ROOT_URL}/logs?apikey={API_KEY}",
            json={
                "associated_job_id": JOB_ID,
                "level": "info",
                "service": "test",
                "node": NODE_ID,
                "code": "test",
                "message": "test message",
                "call_stack": "test callstack",
            },
        )

    @mock.patch("ltc_client.api.requests")
    def test_get_job(self, mock_requests):
        api.get_job(JOB_ID)
        mock_requests.get.assert_called_with(
            url=f"{ROOT_URL}/jobs/{JOB_ID}?apikey={API_KEY}",
        )

    @mock.patch("ltc_client.api.requests")
    def test_update_job_status(self, mock_requests):
        api.update_job_status(JOB_ID, JOB_STATUS)
        mock_requests.put.assert_called_with(
            url=f"{ROOT_URL}/jobs/{JOB_ID}/status/{JOB_STATUS}?node_id={NODE_ID}&apikey={API_KEY}&percentage_complete=None"
        )

    @mock.patch("ltc_client.api.requests")
    def test_get_job_artifact_not_found(self, mock_requests):
        with self.assertRaises(Exception):
            api.get_job_artifact(JOB_ID, JOB_ARTIFACT_ID)
        mock_requests.get.assert_called_with(
            url=f"{ROOT_URL}/jobs/{JOB_ID}?apikey={API_KEY}",
        )

    @mock.patch("ltc_client.api.requests")
    def test_get_promoted_job_artifact_raise(self, mock_requests):
        with self.assertRaises(Exception):
            api.get_promoted_job_artifact("12", "34")
        mock_requests.get.assert_called_with(
            url=f"{ROOT_URL}/jobs/12?apikey={API_KEY}",
        )

    @mock.patch("ltc_client.api.requests")
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

    @mock.patch("ltc_client.api.requests")
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

    @mock.patch("ltc_client.api.requests")
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

    @mock.patch("ltc_client.api.requests")
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

    @mock.patch("ltc_client.api.requests")
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

    @mock.patch("ltc_client.api.requests")
    def test_promote_job_artifact(self, mock_requests):
        api.promote_job_artifact(JOB_ID, JOB_ARTIFACT_ID)
        mock_requests.put.assert_called_with(
            url=f"{ROOT_URL}/jobs/{JOB_ID}/artifacts/{JOB_ARTIFACT_ID}/promote?apikey={API_KEY}",
        )

    def test_tae_model(self):
        jobdata = ltc_client.NameQuantityPair(
            "section",
            "name",
            ltc_client.Quantity(
                magnitude=[4242],
                units=[ltc_client.Unit("millimeter", 2), ltc_client.Unit("second", -1)],
                shape=[1],
            ),
        )

        asDict = jobdata.to_dict()
        self.assertEqual(asDict["section"], "section")
        self.assertEqual(asDict["name"], "name")

    def test_Quantity_from_pint_value(self):
        import pint

        inval = pint.Quantity(42, "millimeter")
        outval = ltc_client.Quantity(inval).to_dict()
        self.assertEqual(outval["magnitude"], [42])
        self.assertEqual(outval["units"], [{"exponent": 1, "name": "millimeter"}])

    def test_Qauntity_from_mulitdim_pint_value(self):
        import numpy as np
        import pint

        inval = np.ones((2, 2, 2)) * pint.Quantity(1.0, "tesla")
        outval = ltc_client.Quantity(inval).to_dict()
        self.assertAlmostEqual(
            outval["magnitude"], [1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0]
        )
        self.assertEqual(outval["shape"], [2, 2, 2])
        self.assertEqual(outval["units"], [{"name": "tesla", "exponent": 1}])

    def test_Qauntity_from_mulitdim_pint_value_coerce_shape(self):
        import numpy as np
        import pint

        inval = np.ones((2, 2, 2)) * pint.Quantity(1.0, "tesla")
        outval = ltc_client.Quantity(inval, shape=[2, 4]).to_dict()
        self.assertEqual(outval["shape"], [2, 4])
        self.assertEqual(outval["units"], [{"name": "tesla", "exponent": 1}])

    def test_Qauntity_from_mulitdim_pint_value_invalid_shape(self):
        import numpy as np
        import pint

        inval = np.ones((2, 2, 2)) * pint.Quantity(1.0, "tesla")
        with self.assertRaises(ValueError):
            outval = ltc_client.Quantity(inval, shape=[2, 5]).to_dict()

    def test_Quantity_from_single_value(self):
        outval = ltc_client.Quantity(42, [ltc_client.Unit("millimeter", 2)]).to_dict()
        self.assertEqual(outval["magnitude"], [42])
        self.assertEqual(outval["shape"], [1])

    def test_Quantity_from_numpy_array(self):
        import numpy as np

        start = np.ones((2, 2, 3))
        outval = ltc_client.Quantity(
            start, [ltc_client.Unit("millimeter", 2)]
        ).to_dict()
        self.assertEqual(outval["magnitude"], start.flatten().tolist())
        self.assertEqual(outval["shape"], [2, 2, 3])

    def test_Quantity_from_list(self):
        outval = ltc_client.Quantity(
            [42, 43], [ltc_client.Unit("millimeter", 2)]
        ).to_dict()
        self.assertEqual(outval["magnitude"], [42, 43])
        self.assertEqual(outval["shape"], [2])

    def test_Quantity_with_invalid_shape(self):
        with self.assertRaises(ValueError):
            ltc_client.Quantity([42, 43], [ltc_client.Unit("millimeter", 2)], [2, 2])

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
        jobdata = ltc_client.NameQuantityPair(
            "section",
            "name",
            ltc_client.Quantity(tuple(value.flatten()), units, indat.shape),
        )

        asDict = jobdata.to_dict()
        self.assertEqual(asDict["section"], "section")
        self.assertEqual(asDict["name"], "name")

    def test_decode(self):
        import pint
        import numpy as np

        q = pint.UnitRegistry()

        in_quant = {
            "magnitude": [42, 43],
            "shape": [2],
            "units": [{"name": "millimeter", "exponent": 2}],
        }
        out_quant = ltc_client.decode(in_quant)
        self.assertTrue(np.isclose(out_quant.to(q.mm**2).magnitude, [42.0, 43.0]).all())
        self.assertEqual(
            out_quant.shape,
            tuple(
                [
                    2,
                ]
            ),
        )
        self.assertEqual(out_quant.dimensionality, q.UnitsContainer({"[length]": 2.0}))


class MaterialTestCase(unittest.TestCase):
    @mock.patch("ltc_client.api.requests")
    def test_get_material(self, mock_requests):
        mock_requests.get.return_value.json.return_value = {
            "id": MATERIAL_ID,
            "reference": "www.example.com",
            "name": "test_name",
            "key_words": ["keyword1", "keyword2"],
            "data": [
                {
                    "section": "material_properties",
                    "name": "property1",
                    "value": {
                        "magnitude": [10],
                        "shape": [1],
                        "units": [{"name": "millimeter", "exponent": 1}],
                    },
                }
            ],
        }
        material = api.get_material(MATERIAL_ID)

        mock_requests.get.assert_called_with(
            url=f"{ROOT_URL}/materials/{MATERIAL_ID}?apikey={API_KEY}",
        )

        self.assertEqual(material.id, MATERIAL_ID)
        self.assertEqual(material.reference, "www.example.com")
        self.assertEqual(material.name, "test_name")
        self.assertEqual(material.key_words, ["keyword1", "keyword2"])
        self.assertEqual(
            len(material.material_properties), 1
        )  # Assuming one property in data
        self.assertEqual(material.material_properties["property1"], 10 * Q.mm)

    @mock.patch("ltc_client.api.requests")
    def test_create_material(self, mock_requests):
        api_data = {
            "id": "66018e5d1cd3bd0d3453646f",
            "reference": "www.example.com",
            "name": "test_name",
            "key_words": ["keyword1", "keyword2"],
            "data": [
                {
                    "section": "material_properties",
                    "name": "property1",
                    "value": {
                        "magnitude": [10],
                        "shape": [1],
                        "units": [{"name": "millimeter", "exponent": 1}],
                    },
                }
            ],
        }


if __name__ == "__main__":
    if is_running_under_teamcity():
        runner = TeamcityTestRunner()
    else:
        runner = unittest.TextTestRunner()
    unittest.main(testRunner=runner)
