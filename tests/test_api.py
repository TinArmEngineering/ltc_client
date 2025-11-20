import os
import sys
import mock
import unittest
import pint

from teamcity import is_running_under_teamcity
from teamcity.unittestpy import TeamcityTestRunner

import ltc_client
from ltc_client import (
    Api,
    NameQuantityPair,
    Quantity,
    Unit,
    Log,
    Material,
    Cluster,
    decode,
)

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


class ApiTestCase(unittest.TestCase):
    def setUp(self):
        # Patch requests.Session and create the Api instance after the patch is active
        self.session_patcher = mock.patch("ltc_client.api.requests.Session")
        self.MockSession = self.session_patcher.start()
        self.mock_session = self.MockSession.return_value
        self.api = ltc_client.Api(
            root_url=ROOT_URL, api_key=API_KEY, org_id=ORG_ID, node_id=NODE_ID
        )

    def tearDown(self):
        self.session_patcher.stop()

    def test_create_log(self):
        mock_response = mock.MagicMock()
        mock_response.status_code = 200
        self.mock_session.post.return_value = mock_response

        message = ltc_client.Log(
            associated_job_id=JOB_ID,
            level="info",
            service="test",
            code="test",
            message="test message",
            call_stack="test callstack",
        )

        self.api.create_log(message)
        self.mock_session.post.assert_called_with(
            url=f"{ROOT_URL}/logs",
            params={},
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

    def test_get_job(self):
        mock_response = mock.MagicMock()
        mock_response.status_code = 200
        self.mock_session.get.return_value = mock_response

        self.api.get_job(JOB_ID)
        self.mock_session.get.assert_called_with(
            url=f"{ROOT_URL}/jobs/{JOB_ID}",
        )

    def test_update_job_status(self):
        mock_response = mock.MagicMock()
        mock_response.status_code = 200
        self.mock_session.put.return_value = mock_response

        self.api.update_job_status(JOB_ID, JOB_STATUS)
        self.mock_session.put.assert_called_with(
            url=f"{ROOT_URL}/jobs/{JOB_ID}/status/{JOB_STATUS}",
            params={"node_id": NODE_ID},
        )

    def test_get_job_artifact_not_found(self):
        mock_response = mock.MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"artifacts": []}
        self.mock_session.get.return_value = mock_response

        with self.assertRaises(Exception):
            self.api.get_job_artifact(JOB_ID, JOB_ARTIFACT_ID)
        self.mock_session.get.assert_called_with(
            url=f"{ROOT_URL}/jobs/{JOB_ID}",
        )

    def test_get_promoted_job_artifact_raise(self):
        mock_response = mock.MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"artifacts": []}
        self.mock_session.get.return_value = mock_response

        with self.assertRaises(Exception):
            self.api.get_promoted_job_artifact("12", "34")
        self.mock_session.get.assert_called_with(
            url=f"{ROOT_URL}/jobs/12",
        )

    @mock.patch("time.sleep")
    def test_get_promoted_job_artifact(self, mock_sleep):
        mock_response = mock.MagicMock()
        mock_response.status_code = 200
        # First call returns non-promoted, second returns promoted
        mock_response.json.side_effect = [
            {"artifacts": [{"id": JOB_ARTIFACT_ID, "url": "file://..."}]},
            {
                "artifacts": [
                    {
                        "id": JOB_ARTIFACT_ID,
                        "url": JOB_ARTIFACT_REMOTE_URL,
                    }
                ]
            },
        ]
        self.mock_session.get.return_value = mock_response

        # Call get_promoted_job_artifact fassing a callback function
        self.api.get_promoted_job_artifact(JOB_ID, JOB_ARTIFACT_ID)

        self.assertEqual(self.mock_session.get.call_count, 2)
        self.mock_session.get.assert_called_with(
            url=f"{ROOT_URL}/jobs/{JOB_ID}",
        )

    def test_create_job_artifact(self):
        mock_response = mock.MagicMock()
        mock_response.status_code = 200
        self.mock_session.post.return_value = mock_response

        self.api.create_job_artifact(JOB_ID, JOB_ARTIFACT_TYPE, JOB_ARTIFACT_REMOTE_URL)
        self.mock_session.post.assert_called_with(
            url=f"{ROOT_URL}/jobs/{JOB_ID}/artifacts",
            params={"promote": False},
            json={
                "created_on_node": NODE_ID,
                "type": JOB_ARTIFACT_TYPE,
                "url": JOB_ARTIFACT_REMOTE_URL,
            },
        )

    def test_create_job_artifact_from_file(self):
        mock_response = mock.MagicMock()
        mock_response.status_code = 200
        self.mock_session.post.return_value = mock_response

        self.api.create_job_artifact_from_file(
            JOB_ID, JOB_ARTIFACT_TYPE, JOB_ARTIFACT_FILE_PATH
        )
        self.mock_session.post.assert_called_with(
            url=f"{ROOT_URL}/jobs/{JOB_ID}/artifacts",
            params={"promote": False},
            json={
                "created_on_node": "testnode",
                "type": JOB_ARTIFACT_TYPE,
                "url": JOB_ARTIFACT_FILE_URL,
            },
        )

    def test_create_job_artifact_from_file_promote(self):
        mock_response = mock.MagicMock()
        mock_response.status_code = 200
        self.mock_session.post.return_value = mock_response

        self.api.create_job_artifact_from_file(
            JOB_ID, JOB_ARTIFACT_TYPE, JOB_ARTIFACT_FILE_PATH, True
        )
        self.mock_session.post.assert_called_with(
            url=f"{ROOT_URL}/jobs/{JOB_ID}/artifacts",
            params={"promote": True},
            json={
                "created_on_node": "testnode",
                "type": JOB_ARTIFACT_TYPE,
                "url": JOB_ARTIFACT_FILE_URL,
            },
        )

    def test_update_job_artifact(self):
        mock_response = mock.MagicMock()
        mock_response.status_code = 200
        self.mock_session.put.return_value = mock_response

        self.api.update_job_artifact(
            JOB_ID,
            JOB_ARTIFACT_ID,
            {"type": JOB_ARTIFACT_TYPE, "url": JOB_ARTIFACT_REMOTE_URL},
        )
        self.mock_session.put.assert_called_with(
            url=f"{ROOT_URL}/jobs/{JOB_ID}/artifacts/{JOB_ARTIFACT_ID}",
            json={
                "type": JOB_ARTIFACT_TYPE,
                "url": JOB_ARTIFACT_REMOTE_URL,
            },
        )

    def test_promote_job_artifact(self):
        mock_response = mock.MagicMock()
        mock_response.status_code = 200
        self.mock_session.put.return_value = mock_response

        self.api.promote_job_artifact(JOB_ID, JOB_ARTIFACT_ID)
        self.mock_session.put.assert_called_with(
            url=f"{ROOT_URL}/jobs/{JOB_ID}/artifacts/{JOB_ARTIFACT_ID}/promote",
            params={},
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
    def setUp(self):
        self.session_patcher = mock.patch("ltc_client.api.requests.Session")
        self.MockSession = self.session_patcher.start()
        self.mock_session = self.MockSession.return_value
        self.api = ltc_client.Api(
            root_url=ROOT_URL, api_key=API_KEY, org_id=ORG_ID, node_id=NODE_ID
        )

    def tearDown(self):
        self.session_patcher.stop()

    def test_get_material(self):
        mock_response = mock.MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
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
        self.mock_session.get.return_value = mock_response

        material = self.api.get_material(MATERIAL_ID)

        self.mock_session.get.assert_called_with(
            url=f"{ROOT_URL}/materials/{MATERIAL_ID}",
        )

        self.assertEqual(material.id, MATERIAL_ID)
        self.assertEqual(material.reference, "www.example.com")
        self.assertEqual(material.name, "test_name")
        self.assertEqual(material.key_words, ["keyword1", "keyword2"])
        self.assertEqual(
            len(material.material_properties), 1
        )  # Assuming one property in data
        self.assertEqual(material.material_properties["property1"], 10 * Q.mm)

    def test_create_material(self):
        mock_response = mock.MagicMock()
        mock_response.status_code = 200
        self.mock_session.post.return_value = mock_response

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


class ClusterTestCase(unittest.TestCase):
    def setUp(self):
        self.session_patcher = mock.patch("ltc_client.api.requests.Session")
        self.MockSession = self.session_patcher.start()
        self.mock_session = self.MockSession.return_value
        self.api = ltc_client.Api(
            root_url=ROOT_URL, api_key=API_KEY, org_id=ORG_ID, node_id=NODE_ID
        )

    def tearDown(self):
        self.session_patcher.stop()

    def test_create_cluster(self):
        mock_response = mock.MagicMock()
        mock_response.status_code = 200
        self.mock_session.post.return_value = mock_response

        cluster = ltc_client.Cluster(
            id="cluster1",
            name="TestCluster",
            node_count=5,
            total_cpu_cores=20,
            allocatable_cpu_cores=15,
            total_memory_bytes=64 * 1024**3,
            allocatable_memory_bytes=48 * 1024**3,
            last_seen="2024-01-01T12:00:00Z",
        )

        self.api.create_cluster(cluster)
        self.mock_session.post.assert_called_with(
            url=f"{ROOT_URL}/clusters",
            params={},
            json={
                "id": "cluster1",
                "name": "TestCluster",
                "node_count": 5,
                "total_cpu_cores": 20,
                "allocatable_cpu_cores": 15,
                "total_memory_bytes": 64 * 1024**3,
                "allocatable_memory_bytes": 48 * 1024**3,
                "last_seen": "2024-01-01T12:00:00Z",
            },
        )

    def test_update_cluster(self):
        mock_response = mock.MagicMock()
        mock_response.status_code = 200
        self.mock_session.put.return_value = mock_response

        cluster = ltc_client.Cluster(
            id="cluster1",
            name="UpdatedCluster",
            node_count=6,
            total_cpu_cores=24,
            allocatable_cpu_cores=18,
            total_memory_bytes=128 * 1024**3,
            allocatable_memory_bytes=96 * 1024**3,
            last_seen="2024-01-02T12:00:00Z",
        )

        self.api.update_cluster(cluster)
        self.mock_session.put.assert_called_with(
            url=f"{ROOT_URL}/clusters/cluster1",
            params={},
            json={
                "id": "cluster1",
                "name": "UpdatedCluster",
                "node_count": 6,
                "total_cpu_cores": 24,
                "allocatable_cpu_cores": 18,
                "total_memory_bytes": 128 * 1024**3,
                "allocatable_memory_bytes": 96 * 1024**3,
                "last_seen": "2024-01-02T12:00:00Z",
            },
        )

    def test_get_cluster(self):
        mock_response = mock.MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "id": "cluster1",
            "name": "TestCluster",
            "node_count": 5,
            "total_cpu_cores": 20,
            "allocatable_cpu_cores": 15,
            "total_memory_bytes": 64 * 1024**3,
            "allocatable_memory_bytes": 48 * 1024**3,
            "last_seen": "2024-01-01T12:00:00Z",
        }

        self.mock_session.get.return_value = mock_response

        cluster = self.api.get_cluster("cluster1")
        self.mock_session.get.assert_called_with(
            url=f"{ROOT_URL}/clusters/cluster1",
        )

        self.assertEqual(cluster["id"], "cluster1")
        self.assertEqual(cluster["name"], "TestCluster")
        self.assertEqual(cluster["node_count"], 5)
        self.assertEqual(cluster["total_cpu_cores"], 20)
        self.assertEqual(cluster["allocatable_cpu_cores"], 15)
        self.assertEqual(cluster["total_memory_bytes"], 64 * 1024**3)
        self.assertEqual(cluster["allocatable_memory_bytes"], 48 * 1024**3)
        self.assertEqual(cluster["last_seen"], "2024-01-01T12:00:00Z")

    def test_get_cluster_by_name(self):
        mock_response = mock.MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "id": "cluster1",
            "name": "TestCluster",
            "node_count": 5,
            "total_cpu_cores": 20,
            "allocatable_cpu_cores": 15,
            "total_memory_bytes": 64 * 1024**3,
            "allocatable_memory_bytes": 48 * 1024**3,
            "last_seen": "2024-01-01T12:00:00Z",
        }

        self.mock_session.get.return_value = mock_response

        cluster = self.api.get_cluster_by_name("TestCluster")
        self.mock_session.get.assert_called_with(
            url=f"{ROOT_URL}/clusters/name/TestCluster",
        )

        self.assertEqual(cluster["id"], "cluster1")
        self.assertEqual(cluster["name"], "TestCluster")
        self.assertEqual(cluster["node_count"], 5)
        self.assertEqual(cluster["total_cpu_cores"], 20)
        self.assertEqual(cluster["allocatable_cpu_cores"], 15)
        self.assertEqual(cluster["total_memory_bytes"], 64 * 1024**3)
        self.assertEqual(cluster["allocatable_memory_bytes"], 48 * 1024**3)
        self.assertEqual(cluster["last_seen"], "2024-01-01T12:00:00Z")

    def test_delete_cluster(self):
        mock_response = mock.MagicMock()
        mock_response.status_code = 200
        self.mock_session.delete.return_value = mock_response

        self.api.delete_cluster("cluster1")
        self.mock_session.delete.assert_called_with(
            url=f"{ROOT_URL}/clusters/cluster1",
        )


if __name__ == "__main__":
    if is_running_under_teamcity():
        runner = TeamcityTestRunner()
    else:
        runner = unittest.TextTestRunner()
    unittest.main(testRunner=runner)
