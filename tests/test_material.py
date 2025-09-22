import unittest
from unittest.mock import patch
import pint

from ltc_client.material import Material

Q = pint.get_application_registry()


class TestMaterial(unittest.TestCase):
    def test_material_initialization(self):
        # Test default initialization
        material = Material(name="test_name", reference="www.example.com", id="mat-1")
        self.assertEqual(material.name, "test_name")
        self.assertEqual(material.reference, "www.example.com")
        self.assertEqual(material.id, "mat-1")
        self.assertEqual(material.key_words, [])
        self.assertEqual(material.material_properties, {})

    def test_initialization_with_properties(self):
        material = Material(
            name="test_name",
            reference="www.example.com",
            key_words=["keyword1", "keyword2"],
            material_properties={"property1": 10 * Q.mm},
        )
        self.assertEqual(material.name, "test_name")
        self.assertEqual(material.reference, "www.example.com")
        self.assertEqual(material.key_words, ["keyword1", "keyword2"])
        self.assertEqual(material.material_properties, {"property1": 10 * Q.mm})

    def test_initialization_requires_name_and_reference(self):
        with self.assertRaises(TypeError):
            Material(name="test_name")
        with self.assertRaises(TypeError):
            Material(reference="www.example.com")
        # The check `if name is None or reference is None` is for older python versions
        # where keyword-only args could be passed by position.
        # This will now raise a TypeError for missing keyword argument.
        with self.assertRaises(TypeError):
            Material(name="test_name", reference=None)

    def test_material_to_api_compound_units(self):
        material = Material(
            name="test_name",
            reference="www.example.com",
            key_words=["keyword1", "keyword2"],
            material_properties={"property1": 10 * Q.V / Q.s},
        )
        api_data = material.to_api()
        self.assertEqual(api_data["name"], "test_name")
        self.assertEqual(api_data["reference"], "www.example.com")
        self.assertEqual(api_data["key_words"], ["keyword1", "keyword2"])
        self.assertIsInstance(api_data["data"], list)
        self.assertEqual(len(api_data["data"]), 1)
        self.assertEqual(api_data["data"][0]["section"], "material_properties")
        self.assertEqual(api_data["data"][0]["name"], "property1")
        self.assertEqual(api_data["data"][0]["value"]["magnitude"], [10.0])
        self.assertEqual(api_data["data"][0]["value"]["shape"], [1])
        self.assertCountEqual(
            api_data["data"][0]["value"]["units"],
            [{"name": "volt", "exponent": 1}, {"name": "second", "exponent": -1}],
        )

    def test_material_to_api_simple_units(self):
        material = Material(
            name="test_name",
            reference="www.example.com",
            key_words=["keyword1", "keyword2"],
            material_properties={"property1": 10 * Q.kg},
        )
        api_data = material.to_api()
        self.assertEqual(api_data["name"], "test_name")
        self.assertEqual(api_data["reference"], "www.example.com")
        self.assertEqual(api_data["key_words"], ["keyword1", "keyword2"])
        self.assertIsInstance(api_data["data"], list)
        self.assertEqual(len(api_data["data"]), 1)
        self.assertEqual(api_data["data"][0]["section"], "material_properties")
        self.assertEqual(api_data["data"][0]["name"], "property1")
        self.assertEqual(api_data["data"][0]["value"]["magnitude"], [10.0])
        self.assertEqual(api_data["data"][0]["value"]["shape"], [1])
        self.assertCountEqual(
            api_data["data"][0]["value"]["units"],
            [{"name": "kilogram", "exponent": 1}],
        )

    def test_material_from_api_with_simple_units(self):
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
        material = Material.from_api(api_data)
        self.assertEqual(material.name, "test_name")
        self.assertEqual(material.reference, "www.example.com")
        self.assertEqual(material.key_words, ["keyword1", "keyword2"])
        self.assertEqual(material.material_properties["property1"], 0.01 * Q.m)
        self.assertEqual(material.id, "66018e5d1cd3bd0d3453646f")

    def test_material_from_api_with_compound_units(self):
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
                        "units": [
                            {"name": "millimeter", "exponent": 1},
                            {"name": "seconds", "exponent": -1},
                        ],
                    },
                }
            ],
        }
        material = Material.from_api(api_data)
        self.assertEqual(material.name, "test_name")
        self.assertEqual(material.reference, "www.example.com")
        self.assertEqual(material.key_words, ["keyword1", "keyword2"])
        self.assertEqual(material.material_properties["property1"], 0.01 * Q.m / Q.s)
        self.assertEqual(material.id, "66018e5d1cd3bd0d3453646f")

    def test_material_from_api_with_optional_fields(self):
        # Test with missing reference
        api_data_no_ref = {
            "id": "mat-1",
            "name": "test_name",
            "key_words": [],
            "data": [],
        }
        material = Material.from_api(api_data_no_ref)
        self.assertEqual(material.reference, "")

        # Test with missing key_words
        api_data_no_keywords = {
            "id": "mat-1",
            "name": "test_name",
            "reference": "ref",
            "data": [],
        }
        material = Material.from_api(api_data_no_keywords)
        self.assertEqual(material.key_words, [])

        # Test with missing id
        api_data_no_id = {
            "name": "test_name",
            "reference": "ref",
            "key_words": [],
            "data": [],
        }
        material = Material.from_api(api_data_no_id)
        self.assertIsNone(material.id)

    def test_from_api_ignores_other_data_sections(self):
        api_data = {
            "id": "mat-1",
            "name": "test_name",
            "reference": "ref",
            "data": [
                {
                    "section": "other_section",
                    "name": "some_prop",
                    "value": {"magnitude": [1], "shape": [1], "units": []},
                }
            ],
        }
        material = Material.from_api(api_data)
        self.assertEqual(material.material_properties, {})

    def test_material_to_api_with_failing_compound_unit(self):
        """
        This test replicates the bug where complex compound units are not
        deconstructed correctly by Material.to_api().
        """
        # it is not a quanity issue, but when it is instantiated. For example:
        vlc_quantity = 1.0 * Q.kg**-1 * Q.m**-1 * Q.s**2 * Q.A**2

        material = Material(
            name="test_fail",
            reference="test_ref",
        )
        material.material_properties = {"VLC": vlc_quantity}

        # Call the method that exhibits the bug
        api_data = material.to_api()

        # This assertion will fail with the current implementation.
        # The buggy implementation will produce a single unit:
        # [{'name': 'ampere ** 2 * second ** 2 / kilogram / meter', 'exponent': 1}]
        expected_units = [
            {"name": "kilogram", "exponent": -1},
            {"name": "meter", "exponent": -1},
            {"name": "second", "exponent": 2},
            {"name": "ampere", "exponent": 2},
        ]

        vlc_data = next(
            (item for item in api_data["data"] if item["name"] == "VLC"), None
        )
        self.assertIsNotNone(vlc_data, "VLC data not found in API output")
        self.assertCountEqual(vlc_data["value"]["units"], expected_units)


if __name__ == "__main__":
    unittest.main()
