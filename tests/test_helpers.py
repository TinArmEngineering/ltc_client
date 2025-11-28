import json
import unittest
from unittest.mock import patch, MagicMock
import warnings
import numpy as np

from ltc_client.helpers import decode, encode
from ltc_client.helpers import Machine, Job, JobBatchProgressListener

from teamcity import is_running_under_teamcity
from teamcity.unittestpy import TeamcityTestRunner
import pint

Q = pint.get_application_registry()


class TestDecodeFunction(unittest.TestCase):
    @patch("ltc_client.helpers.logger")
    def test_decode_with_single_magnitude(self, mock_logger):
        """Test decoding of a single scalar value."""
        # Setup
        enc = {
            "magnitude": [42],
            "shape": (1,),
            "units": [{"name": "meter", "exponent": 1}],
        }

        # Execute
        result = decode(enc)

        # Verify
        expected_quant = Q.Quantity(42, "meter")
        self.assertEqual(result, expected_quant)
        mock_logger.debug.assert_called()

    @patch("ltc_client.helpers.logger")
    def test_decode_with_multiple_magnitudes(self, mock_logger):
        """Test decoding of a multi-element array value."""
        # Setup
        enc = {
            "magnitude": [1, 2, 3, 4],
            "shape": (2, 2),
            "units": [{"name": "second", "exponent": -1}],
        }

        # Execute
        result = decode(enc)

        # Verify
        expected_array = np.array([1, 2, 3, 4], dtype=np.float64).reshape((2, 2))
        expected_quant = Q.Quantity(expected_array, "1/s")
        np.testing.assert_array_equal(result.magnitude, expected_quant.magnitude)
        self.assertEqual(result.units, expected_quant.units)
        mock_logger.debug.assert_called()

    @patch("ltc_client.helpers.logger")
    def test_decode_with_0d_array_like(self, mock_logger):
        """Test decoding of a 0-dimensional array-like structure."""
        # Setup for a 0-d array (scalar)
        enc = {
            "magnitude": [42.0],
            "shape": [],  # This shape is ignored by the scalar path in decode
            "units": [{"name": "meter", "exponent": 1}],
        }

        # Execute
        result = decode(enc)

        # Verify it's treated as a scalar
        expected_quant = Q.Quantity(42.0, "meter")
        self.assertEqual(result, expected_quant)
        self.assertTrue(np.isscalar(result.magnitude))
        # assert that the assignment to c is possible without warnings or errors
        b = np.array([[3.14]])
        c = np.random.rand(10)
        # This should NOT raise a warning because result.magnitude is a scalar
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")  # Capture all warnings
            c[0] = result.magnitude
            # Verify that no warnings were caught
            self.assertEqual(
                len(w), 0, "Assignment of scalar magnitude should not raise a warning."
            )

        # This SHOULD raise a DeprecationWarning for a non-scalar array
        with self.assertWarns(DeprecationWarning):
            c[0] = b

    @patch("ltc_client.helpers.logger")
    def test_decode_with_1_element_array_like(self, mock_logger):
        """Test decoding of a 1-element array-like structure."""
        # Setup for a 1-element 1D array
        enc = {
            "magnitude": [3.14],
            "shape": [1],  # This shape is ignored by the scalar path in decode
            "units": [{"name": "radian", "exponent": 1}],
        }

        # Execute
        result = decode(enc)

        # Verify it's treated as a scalar
        expected_quant = Q.Quantity(3.14, "radian")
        self.assertEqual(result, expected_quant)
        self.assertTrue(np.isscalar(result.magnitude))
        # assert that the assignment to c is possible without warnings or errors
        b = np.array([[3.14]])
        c = np.random.rand(10)
        # This should NOT raise a warning because result.magnitude is a scalar
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")  # Capture all warnings
            c[0] = result.magnitude
            # Verify that no warnings were caught
            self.assertEqual(
                len(w), 0, "Assignment of scalar magnitude should not raise a warning."
            )

        # This SHOULD raise a DeprecationWarning for a non-scalar array
        with self.assertWarns(DeprecationWarning):
            c[0] = b


class TestEncodeFunction(unittest.TestCase):
    """Test the encode function and encode-decode round trips."""

    def test_encode_scalar_quantity(self):
        """Test encoding a scalar quantity."""
        # Setup
        quantity = 42 * Q.meter

        # Execute
        result = encode(quantity)

        # Verify structure
        self.assertIn("magnitude", result)
        self.assertIn("units", result)
        self.assertIn("shape", result)
        self.assertEqual(result["magnitude"], [42.0])
        self.assertEqual(result["shape"], ())
        self.assertEqual(result["units"], [{"name": "meter", "exponent": 1}])
        self.assertEqual(result["unit_string"], "m")

    def test_encode_array_quantity(self):
        """Test encoding an array quantity."""
        # Setup
        array = np.array([1, 2, 3, 4], dtype=np.float64).reshape((2, 2))
        quantity = array * Q("1/s")

        # Execute
        result = encode(quantity)

        # Verify structure
        self.assertEqual(result["magnitude"], [1.0, 2.0, 3.0, 4.0])
        self.assertEqual(result["shape"], (2, 2))
        self.assertEqual(result["units"], [{"name": "second", "exponent": -1}])
        self.assertEqual(result["unit_string"], "1/s")

    def test_encode_complex_units(self):
        """Test encoding a quantity with complex compound units."""
        # Setup
        quantity = 100 * Q.N * Q.m  # Newton * meter = force * distance

        # Execute
        result = encode(quantity)

        # Verify structure
        self.assertIn("magnitude", result)
        self.assertIn("units", result)
        self.assertEqual(result["magnitude"], [100.0])
        # Check that both 'newton' and 'meter' are in the units (order may vary)
        unit_names = {u["name"] for u in result["units"]}
        self.assertIn("newton", unit_names)
        self.assertIn("meter", unit_names)

    def test_encode_dimensionless_quantity(self):
        """Test encoding a dimensionless quantity (count)."""
        # Setup
        quantity = 42 * Q.count

        # Execute
        result = encode(quantity)

        # Verify structure
        self.assertEqual(result["magnitude"], [42.0])
        self.assertEqual(result["shape"], ())
        self.assertEqual(result["units"], [{"name": "count", "exponent": 1}])
        self.assertEqual(result["unit_string"], "count")

    def test_encode_single_element_array(self):
        """Test encoding a single-element array quantity."""
        # Setup
        array = np.array([3.14])
        quantity = array * Q.radian

        # Execute
        result = encode(quantity)

        # Verify structure
        self.assertEqual(result["magnitude"], [3.14])
        self.assertEqual(result["shape"], (1,))
        self.assertEqual(result["units"], [{"name": "radian", "exponent": 1}])
        self.assertEqual(result["unit_string"], "rad")

    def test_encode_3d_array(self):
        """Test encoding a 3D array quantity."""
        # Setup
        array = np.arange(24, dtype=np.float64).reshape((2, 3, 4))
        quantity = array * Q.millimeter

        # Execute
        result = encode(quantity)

        # Verify structure
        self.assertEqual(len(result["magnitude"]), 24)
        self.assertEqual(result["shape"], (2, 3, 4))
        self.assertEqual(result["units"], [{"name": "millimeter", "exponent": 1}])
        self.assertEqual(result["unit_string"], "mm")
        # Verify magnitude is flattened
        np.testing.assert_array_equal(
            result["magnitude"], np.arange(24, dtype=np.float64).tolist()
        )

    def test_round_trip_encode_decode_scalar(self):
        """Test encode-decode round trip for scalar quantity."""
        # Setup
        original = 42.5 * Q.meter

        # Execute
        encoded = encode(original)
        decoded = decode(encoded)

        # Verify
        self.assertEqual(decoded, original)

    def test_round_trip_encode_decode_array(self):
        """Test encode-decode round trip for array quantity."""
        # Setup
        array = np.array([1.5, 2.5, 3.5, 4.5], dtype=np.float64).reshape((2, 2))
        original = array * Q("1/s")

        # Execute
        encoded = encode(original)
        decoded = decode(encoded)

        # Verify
        np.testing.assert_array_almost_equal(decoded.magnitude, original.magnitude)
        self.assertEqual(decoded.units, original.units)

    def test_round_trip_encode_decode_complex_units(self):
        """Test encode-decode round trip for complex compound units."""
        # Setup
        original = 50 * Q.N * Q.m

        # Execute
        encoded = encode(original)
        decoded = decode(encoded)

        # Verify (use to_base_units for comparison due to unit simplification)
        self.assertEqual(decoded.to_base_units(), original.to_base_units())

    def test_round_trip_decode_encode_scalar(self):
        """Test decode-encode round trip for scalar quantity."""
        # Setup
        original_enc = {
            "magnitude": [42.0],
            "shape": (),
            "units": [{"name": "meter", "exponent": 1}],
        }

        # Execute
        decoded = decode(original_enc)
        encoded = encode(decoded)

        # Verify
        self.assertEqual(encoded["magnitude"], original_enc["magnitude"])
        self.assertEqual(encoded["shape"], original_enc["shape"])
        self.assertEqual(encoded["units"], original_enc["units"])

    def test_round_trip_decode_encode_array(self):
        """Test decode-encode round trip for array quantity."""
        # Setup
        original_enc = {
            "magnitude": [1.0, 2.0, 3.0, 4.0],
            "shape": (2, 2),
            "units": [{"name": "second", "exponent": -1}],
        }

        # Execute
        decoded = decode(original_enc)
        encoded = encode(decoded)

        # Verify
        self.assertEqual(encoded["magnitude"], original_enc["magnitude"])
        self.assertEqual(encoded["shape"], original_enc["shape"])
        self.assertEqual(encoded["units"], original_enc["units"])

    def test_round_trip_decode_encode_3d_array(self):
        """Test decode-encode round trip for 3D array quantity."""
        # Setup
        magnitude_list = list(np.arange(24, dtype=np.float64))
        original_enc = {
            "magnitude": magnitude_list,
            "shape": (2, 3, 4),
            "units": [{"name": "millimeter", "exponent": 1}],
        }

        # Execute
        decoded = decode(original_enc)
        encoded = encode(decoded)

        # Verify
        self.assertEqual(encoded["magnitude"], original_enc["magnitude"])
        self.assertEqual(encoded["shape"], original_enc["shape"])
        self.assertEqual(encoded["units"], original_enc["units"])

    def test_encode_preserves_magnitude_precision(self):
        """Test that encode preserves floating-point precision."""
        # Setup
        original = 3.141592653589793 * Q.meter

        # Execute
        encoded = encode(original)

        # Verify
        self.assertAlmostEqual(encoded["magnitude"][0], 3.141592653589793)

    def test_encode_negative_exponent_units(self):
        """Test encoding quantities with negative exponent units."""
        # Setup
        quantity = 10 * Q.meter / Q.second

        # Execute
        result = encode(quantity)

        # Verify
        self.assertEqual(result["magnitude"], [10.0])
        # Check for meter with exponent 1 and second with exponent -1
        units_dict = {u["name"]: u["exponent"] for u in result["units"]}
        self.assertEqual(units_dict.get("meter"), 1)
        self.assertEqual(units_dict.get("second"), -1)

    def test_encode_multiple_same_units(self):
        """Test encoding quantities with multiple instances of same unit (e.g., m²)."""
        # Setup
        quantity = 25 * Q.meter**2

        # Execute
        result = encode(quantity)

        # Verify
        self.assertEqual(result["magnitude"], [25.0])
        # Should have meter with exponent 2
        units_dict = {u["name"]: u["exponent"] for u in result["units"]}
        self.assertEqual(units_dict.get("meter"), 2)


class TestJobBatchProgressListener(unittest.TestCase):
    def test_on_message_calls_callback_for_tracked_job(self):
        # Setup
        job_ids = ["job-1", "job-2"]
        mock_callback = MagicMock()
        listener = JobBatchProgressListener(job_ids, mock_callback)

        target_job_id = "job-1"
        payload = {"status": "running"}
        message = json.dumps(payload).encode()
        headers = [(b"destination", f"/topic/{target_job_id}.worker.progress".encode())]
        frame = MagicMock(header=headers, message=message)

        # Execute
        listener.on_message(frame)

        # Verify
        mock_callback.assert_called_once_with(target_job_id, payload)

    def test_on_message_ignores_untracked_job(self):
        # Setup
        job_ids = ["job-1", "job-2"]
        mock_callback = MagicMock()
        listener = JobBatchProgressListener(job_ids, mock_callback)

        untracked_job_id = "job-3"
        payload = {"status": "running"}
        message = json.dumps(payload).encode()
        headers = [
            (b"destination", f"/topic/{untracked_job_id}.worker.progress".encode())
        ]
        frame = MagicMock(header=headers, message=message)

        # Execute
        listener.on_message(frame)

        # Verify
        mock_callback.assert_not_called()

    def test_on_message_handles_malformed_destination(self):
        # Setup
        job_ids = ["job-1"]
        mock_callback = MagicMock()
        listener = JobBatchProgressListener(job_ids, mock_callback)

        payload = {"status": "running"}
        message = json.dumps(payload).encode()
        headers = [(b"destination", b"/topic/")]  # Malformed
        frame = MagicMock(header=headers, message=message)

        # Execute
        listener.on_message(frame)

        # Verify
        mock_callback.assert_not_called()

    def test_on_message_handles_malformed_json(self):
        # Setup
        job_ids = ["job-1"]
        mock_callback = MagicMock()
        listener = JobBatchProgressListener(job_ids, mock_callback)

        target_job_id = "job-1"
        message = b"this is not json"
        headers = [(b"destination", f"/topic/{target_job_id}.worker.progress".encode())]
        frame = MagicMock(header=headers, message=message)

        # Execute
        listener.on_message(frame)

        # Verify
        mock_callback.assert_not_called()

    def test_on_message_parses_time_prefixed_json(self):
        # Setup
        job_ids = ["job-1"]
        mock_callback = MagicMock()
        listener = JobBatchProgressListener(job_ids, mock_callback)

        target_job_id = "job-1"
        payload = {"status": "complete"}
        message_str = f"12:34:56 - INFO - {json.dumps(payload)}"
        message = message_str.encode()
        headers = [(b"destination", f"/topic/{target_job_id}.worker.progress".encode())]
        frame = MagicMock(header=headers, message=message)

        # Execute
        listener.on_message(frame)

        # Verify
        mock_callback.assert_called_once_with(target_job_id, payload)


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

    def test_job_netlist_property(self):
        """Test the getter and setter for the netlist property."""
        with patch.object(Job, "generate_title", return_value="test-title"):
            job = Job(
                self.mock_machine, self.mock_operating_point, self.mock_simulation
            )
            # Test initial value
            self.assertEqual(job.netlist, None)

            # Test setting and getting
            netlist_data = {"component": "resistor", "value": 100}
            job.netlist = netlist_data
            self.assertEqual(job.netlist, netlist_data)

    def test_job_to_api_with_string_data(self):
        """Test that to_api includes netlist and mesh_reuse_series."""
        with patch.object(Job, "generate_title", return_value="test-title"):
            job = Job(
                self.mock_machine, self.mock_operating_point, self.mock_simulation
            )

        netlist_data = {
            "I_A": {
                "circuit": 1,
                "neg_pin": 1,
                "pos_pin": 2,
                "value": {
                    "magnitude": [1],
                    "shape": [1],
                    "units": [{"exponent": 1, "name": "ampere"}],
                },
            },
            "I_B": {
                "circuit": 1,
                "neg_pin": 1,
                "pos_pin": 3,
                "value": {
                    "magnitude": [1],
                    "shape": [1],
                    "units": [{"exponent": 1, "name": "ampere"}],
                },
            },
            "I_C": {
                "circuit": 1,
                "neg_pin": 1,
                "pos_pin": 4,
                "value": {
                    "magnitude": [1],
                    "shape": [1],
                    "units": [{"exponent": 1, "name": "ampere"}],
                },
            },
            "R_A": {
                "circuit": 1,
                "neg_pin": 7,
                "pos_pin": 1,
                "value": {
                    "magnitude": [0.01],
                    "shape": [],
                    "units": [{"exponent": 1, "name": "ohm"}],
                },
            },
            "R_B": {
                "circuit": 1,
                "neg_pin": 9,
                "pos_pin": 1,
                "value": {
                    "magnitude": [0.01],
                    "shape": [],
                    "units": [{"exponent": 1, "name": "ohm"}],
                },
            },
            "R_C": {
                "circuit": 1,
                "neg_pin": 10,
                "pos_pin": 1,
                "value": {
                    "magnitude": [0.01],
                    "shape": [],
                    "units": [{"exponent": 1, "name": "ohm"}],
                },
            },
            "slot_0_area_layer_0": {
                "circuit": 1,
                "coil": {
                    "additional_coil_resistance": {
                        "magnitude": [0],
                        "shape": [1],
                        "units": [{"exponent": 1, "name": "ohm"}],
                    },
                    "turns_per_coil": 25,
                },
                "component_number": 1,
                "master_body_list": ["slot_0_area_layer_0"],
                "neg_pin": 4,
                "pos_pin": 5,
            },
            "slot_0_area_layer_1": {
                "circuit": 1,
                "coil": {
                    "additional_coil_resistance": {
                        "magnitude": [0],
                        "shape": [1],
                        "units": [{"exponent": 1, "name": "ohm"}],
                    },
                    "turns_per_coil": 25,
                },
                "component_number": 2,
                "master_body_list": ["slot_0_area_layer_1"],
                "neg_pin": 6,
                "pos_pin": 2,
            },
            "slot_1_area_layer_0": {
                "circuit": 1,
                "coil": {
                    "additional_coil_resistance": {
                        "magnitude": [0],
                        "shape": [1],
                        "units": [{"exponent": 1, "name": "ohm"}],
                    },
                    "turns_per_coil": 25,
                },
                "component_number": 3,
                "master_body_list": ["slot_1_area_layer_0"],
                "neg_pin": 6,
                "pos_pin": 7,
            },
            "slot_1_area_layer_1": {
                "circuit": 1,
                "coil": {
                    "additional_coil_resistance": {
                        "magnitude": [0],
                        "shape": [1],
                        "units": [{"exponent": 1, "name": "ohm"}],
                    },
                    "turns_per_coil": 25,
                },
                "component_number": 4,
                "master_body_list": ["slot_1_area_layer_1"],
                "neg_pin": 8,
                "pos_pin": 3,
            },
            "slot_2_area_layer_0": {
                "circuit": 1,
                "coil": {
                    "additional_coil_resistance": {
                        "magnitude": [0],
                        "shape": [1],
                        "units": [{"exponent": 1, "name": "ohm"}],
                    },
                    "turns_per_coil": 25,
                },
                "component_number": 5,
                "master_body_list": ["slot_2_area_layer_0"],
                "neg_pin": 8,
                "pos_pin": 9,
            },
            "slot_2_area_layer_1": {
                "circuit": 1,
                "coil": {
                    "additional_coil_resistance": {
                        "magnitude": [0],
                        "shape": [1],
                        "units": [{"exponent": 1, "name": "ohm"}],
                    },
                    "turns_per_coil": 25,
                },
                "component_number": 6,
                "master_body_list": ["slot_2_area_layer_1"],
                "neg_pin": 10,
                "pos_pin": 5,
            },
        }

        job.netlist = netlist_data

        series_id = "test-series-xyz"
        job.mesh_reuse_series = series_id

        api_data = job.to_api()

        expected_string_data = [
            {"name": "mesh_reuse_series", "value": series_id},
            {"name": "netlist", "value": json.dumps(netlist_data)},
        ]

        self.assertIn("string_data", api_data)
        # Sort for comparison as dict item order is not guaranteed
        self.assertEqual(
            sorted(api_data["string_data"], key=lambda x: x["name"]),
            sorted(expected_string_data, key=lambda x: x["name"]),
        )

    def test_job_repr(self):
        with patch.object(Job, "generate_title", return_value="test-title"):
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

        with patch.object(Job, "generate_title", return_value="test-title"):
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

    def test_mesh_reuse_to_api(self):
        with patch.object(Job, "generate_title", return_value="test-title"):
            job = Job(
                self.mock_machine, self.mock_operating_point, self.mock_simulation
            )
            # Test setter
            job.mesh_reuse_series = "new-series"
            result = job.to_api()
            self.assertIn(
                {"name": "mesh_reuse_series", "value": "new-series"},
                result["string_data"],
            )
            # Test default value
            job = Job(
                self.mock_machine, self.mock_operating_point, self.mock_simulation
            )
            result = job.to_api()
            self.assertIn(
                {"name": "mesh_reuse_series", "value": job.mesh_reuse_series},
                result["string_data"],
            )

    def test_job_to_api_from_api_round_trip(self):
        """Test that Job.to_api() and Job.from_api() produce equivalent objects."""
        # Create real pint quantities for testing
        operating_point = {"speed": 1000 * Q.rpm, "torque": 50 * Q.N * Q.m}
        simulation = {"these": 1 * Q.count}
        stator = {"all": 2.0 * Q.mm}
        rotor = {"are": 3.0 * Q.feet}
        winding = {"different": 4.0 * Q.furlong}
        materials = {
            "rotor_lamination": "test_material_1",
            "stator_slot_winding": "test_material_2",
        }

        machine = Machine(stator, rotor, winding, materials)
        original_job = Job(
            machine, operating_point, simulation, title="test-round-trip"
        )
        original_job.netlist = {"test": "netlist_data"}
        original_job.mesh_reuse_series = "test-series"

        # Convert to API format
        api_dict = original_job.to_api()
        # Ensure 'id' is present for from_api
        api_dict["id"] = "test-job-id-123"

        # Create new job instance and load from API
        new_job = Job.from_api(api_dict)

        # Compare attributes
        self.assertEqual(new_job.title, original_job.title)
        self.assertEqual(new_job.type, original_job.type)
        self.assertEqual(new_job.status, original_job.status)
        self.assertIsInstance(new_job.id, str)
        self.assertEqual(new_job._string_data, original_job._string_data)
        self.assertEqual(new_job.netlist, original_job.netlist)
        self.assertEqual(new_job.mesh_reuse_series, original_job.mesh_reuse_series)
        self.assertIsInstance(new_job.machine, Machine)

        # Compare operating point quantities
        for key in original_job.operating_point:
            self.assertEqual(
                new_job.operating_point[key], original_job.operating_point[key]
            )

        # Compare simulation quantities
        for key in original_job.simulation:
            self.assertEqual(
                new_job.simulation[key].to_base_units(),
                original_job.simulation[key].to_base_units(),
            )

        # Compare machine components
        for key, value in original_job.machine.stator.items():
            self.assertIn(key, new_job.machine.stator)
            self.assertEqual(
                new_job.machine.stator[key].to_base_units(),
                value.to_base_units(),
            )
        for key, value in original_job.machine.rotor.items():
            self.assertIn(key, new_job.machine.rotor)
            self.assertEqual(
                new_job.machine.rotor[key].to_base_units(),
                value.to_base_units(),
            )
        for key, value in original_job.machine.winding.items():
            self.assertIn(key, new_job.machine.winding)
            self.assertEqual(
                new_job.machine.winding[key].to_base_units(),
                value.to_base_units(),
            )

        self.assertEqual(new_job.machine.materials, original_job.machine.materials)


if __name__ == "__main__":
    if is_running_under_teamcity():
        runner = TeamcityTestRunner()
    else:
        runner = unittest.TextTestRunner()
    unittest.main(testRunner=runner)
