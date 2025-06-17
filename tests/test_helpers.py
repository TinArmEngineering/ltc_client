import unittest
from unittest.mock import patch, MagicMock
import numpy as np

from ltc_client.helpers import decode
from ltc_client.helpers import Machine, Job

from teamcity import is_running_under_teamcity
from teamcity.unittestpy import TeamcityTestRunner


class CustomMock(MagicMock):
    def __format__(self, format_spec):
        # Implement your formatting logic here
        # For example, return a fixed string or dynamically handle the format_spec
        return "Mocked Format"


class TestDecodeFunction(unittest.TestCase):
    @patch("ltc_client.helpers.q.Quantity.from_tuple")
    @patch("ltc_client.helpers.logger")
    def test_decode_with_single_magnitude(self, mock_logger, mock_from_tuple):
        # Setup
        enc = {
            "magnitude": [42],
            "shape": (1,),
            "units": [{"name": "meter", "exponent": 1}],
        }
        mock_quant = CustomMock()
        mock_from_tuple.return_value = mock_quant

        # Execute
        result = decode(enc)

        # Verify
        mock_from_tuple.assert_called_once_with((42, (("meter", 1),)))
        self.assertEqual(result, mock_quant)
        mock_quant.ito_base_units.assert_called_once()
        mock_logger.debug.assert_called()

    @patch("ltc_client.helpers.q.Quantity.from_tuple")
    @patch("ltc_client.helpers.logger")
    def test_decode_with_multiple_magnitudes(self, mock_logger, mock_from_tuple):
        # Setup
        enc = {
            "magnitude": [1, 2, 3, 4],
            "shape": (2, 2),
            "units": [{"name": "second", "exponent": -1}],
        }
        expected_array = np.array([1, 2, 3, 4], dtype=np.float64).reshape((2, 2))
        mock_quant = CustomMock()
        mock_from_tuple.return_value = mock_quant

        # Execute
        result = decode(enc)

        # Verify
        np.testing.assert_array_equal(
            mock_from_tuple.call_args[0][0][0], expected_array
        )
        self.assertEqual(mock_from_tuple.call_args[0][0][1], (("second", -1),))
        self.assertEqual(result, mock_quant)
        mock_quant.ito_base_units.assert_called_once()
        mock_logger.debug.assert_called()


class TestMachine(unittest.TestCase):
    def setUp(self):
        # Mocking the components with MagicMock to simulate their behavior
        self.stator = [
            {
                "section": "stator",
                "name": "slot_liner_thickness",
                "value": {
                    "magnitude": [0.125],
                    "units": [{"name": "millimeter", "exponent": 1}],
                    "unit_string": "mm",
                },
            }
        ]
        self.rotor = [
            {
                "section": "rotor",
                "name": "slot_liner_thickness",
                "value": {
                    "magnitude": [0.125],
                    "units": [{"name": "millimeter", "exponent": 1}],
                    "unit_string": "mm",
                },
            }
        ]
        self.winding = [
            {
                "section": "rotor",
                "name": "slot_liner_thickness",
                "value": {
                    "magnitude": [0.125],
                    "units": [{"name": "millimeter", "exponent": 1}],
                    "unit_string": "mm",
                },
            }
        ]

    def test_initialization_with_default_materials(self):
        machine = Machine(self.stator, self.rotor, self.winding)
        self.assertEqual(
            machine.materials["rotor_lamination"], "66018e5d1cd3bd0d3453646f"
        )
        self.assertEqual(
            machine.materials["stator_slot_winding"], "66018e5d1cd3bd0d34536470"
        )

    def test_initialization_with_custom_materials(self):
        custom_materials = {
            "rotor_lamination": "custom1",
            "stator_slot_winding": "custom2",
        }
        machine = Machine(
            self.stator, self.rotor, self.winding, materials=custom_materials
        )
        self.assertEqual(machine.materials["rotor_lamination"], "custom1")
        self.assertEqual(machine.materials["stator_slot_winding"], "custom2")

    # def test_to_api(self):
    #     machine = Machine(self.stator, self.rotor, self.winding)
    #     expected_api_output = [
    #         {"name": "stator", "key": "key1", "quantity": {"magnitude": "value1"}},
    #         {"name": "rotor", "key": "key2", "quantity": {"magnitude": "value2"}},
    #         {"name": "winding", "key": "key3", "quantity": {"magnitude": "value3"}},
    #     ]
    #     api_output = machine.to_api()
    #     # Convert Quantity objects in expected_api_output to their dict representation for comparison
    #     for item in expected_api_output:
    #         item["quantity"] = Quantity(*item["quantity"]["magnitude"]).to_dict()
    #     self.assertEqual(api_output, expected_api_output)


class TestJob(unittest.TestCase):
    def setUp(self):
        # Mock machine object
        self.mock_machine = MagicMock()
        self.mock_machine.to_api.return_value = [
            {"name": "stator", "key": "test_key", "quantity": {"magnitude": 1.0}}
        ]
        self.mock_machine.materials = {
            "rotor_lamination": "66018e5d1cd3bd0d3453646f",
            "stator_slot_winding": "66018e5d1cd3bd0d34536470",
        }

        # Mock operating point and simulation
        self.mock_operating_point = {"speed": MagicMock(), "torque": MagicMock()}
        self.mock_operating_point["speed"].to_tuple.return_value = (1000, (("rpm", 1),))
        self.mock_operating_point["torque"].to_tuple.return_value = (50, (("N*m", 1),))

        self.mock_simulation = {"timestep_intervals": MagicMock()}
        self.mock_simulation["timestep_intervals"].to_tuple.return_value = (
            100,
            (("", 1),),
        )

    def test_job_initialization_with_default_title(self):
        with patch.object(Job, "generate_title", return_value="test-title"):
            job = Job(
                self.mock_machine, self.mock_operating_point, self.mock_simulation
            )

            self.assertEqual(job.title, "test-title")
            self.assertEqual(job.type, "electromagnetic_spmbrl_fscwseg")
            self.assertEqual(job.status, 0)
            self.assertEqual(job.machine, self.mock_machine)
            self.assertEqual(job.operating_point, self.mock_operating_point)
            self.assertEqual(job.simulation, self.mock_simulation)
            self.assertIsInstance(job.mesh_reuse_series, str)

    def test_job_initialization_with_custom_title(self):
        job = Job(
            self.mock_machine,
            self.mock_operating_point,
            self.mock_simulation,
            title="custom-title",
        )

        self.assertEqual(job.title, "custom-title")
        self.assertEqual(job.type, "electromagnetic_spmbrl_fscwseg")
        self.assertEqual(job.status, 0)

    def test_job_initialization_with_mesh_reuse_series(self):
        job = Job(
            self.mock_machine,
            self.mock_operating_point,
            self.mock_simulation,
            mesh_reuse_series="custom-series",
        )

        self.assertEqual(job.mesh_reuse_series, "custom-series")

    def test_mesh_reuse_series_property(self):
        job = Job(self.mock_machine, self.mock_operating_point, self.mock_simulation)

        # Test setter
        job.mesh_reuse_series = "new-series"
        self.assertEqual(job.mesh_reuse_series, "new-series")

        # Test validation
        with self.assertRaises(ValueError):
            job.mesh_reuse_series = 123

    def test_job_repr(self):
        job = Job(
            self.mock_machine,
            self.mock_operating_point,
            self.mock_simulation,
            title="test-job",
        )

        expected_repr = f"Job({self.mock_machine}, {self.mock_operating_point}, {self.mock_simulation})"
        self.assertEqual(repr(job), expected_repr)

    @patch("ltc_client.helpers.NameQuantityPair")
    @patch("ltc_client.helpers.Quantity")
    def test_to_api(self, mock_quantity, mock_name_quantity_pair):
        # Setup mocks
        mock_nqp_instance = MagicMock()
        mock_nqp_instance.to_dict.return_value = {
            "name": "test",
            "key": "test_key",
            "quantity": {"magnitude": 1.0},
        }
        mock_name_quantity_pair.return_value = mock_nqp_instance

        job = Job(
            self.mock_machine,
            self.mock_operating_point,
            self.mock_simulation,
            title="test-job",
        )
        result = job.to_api()

        # Verify structure
        self.assertIn("status", result)
        self.assertIn("title", result)
        self.assertIn("type", result)
        self.assertIn("tasks", result)
        self.assertIn("data", result)
        self.assertIn("materials", result)
        self.assertIn("string_data", result)

        self.assertEqual(result["status"], 0)
        self.assertEqual(result["title"], "test-job")
        self.assertEqual(result["type"], "electromagnetic_spmbrl_fscwseg")
        self.assertEqual(result["tasks"], 11)
        self.assertIsInstance(result["data"], list)
        self.assertIsInstance(result["materials"], list)
        self.assertIsInstance(result["string_data"], list)


if __name__ == "__main__":
    if is_running_under_teamcity():
        runner = TeamcityTestRunner()
    else:
        runner = unittest.TextTestRunner()
    unittest.main(testRunner=runner)
