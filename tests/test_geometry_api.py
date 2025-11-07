import pytest
import requests
from unittest.mock import Mock, patch
import pint

from ltc_client.geometry_api import GeometryApi

Q = pint.get_application_registry()


@pytest.fixture
def geometry_api():
    """Fixture for GeometryApi instance."""
    return GeometryApi("http://test-url")


@pytest.fixture
def mock_response():
    """Fixture for a mock requests.Response object."""
    mock = Mock()
    mock.raise_for_status = Mock()
    return mock


def test_get_fscw_stator_geom_success(geometry_api, mock_response):
    """Test get_fscw_stator_geom successfully returns geometry."""
    with patch("requests.post", return_value=mock_response) as mock_post:
        # Mock the JSON response from the API
        mock_response.json.return_value = {
            "geometry": {
                "geometries": [
                    {"type": "stator_slice", "name": "Stator Slice"},
                    {"type": "stator_wedge", "name": "Stator Wedge"},
                ]
            }
        }

        # Input values with units
        args = {
            "slot_liner_thickness": 0.5 * Q.mm,
            "stator_bore": 100 * Q.mm,
            "tooth_tip_depth": 5 * Q.mm,
            "slot_opening": 3 * Q.mm,
            "tooth_width": 10 * Q.mm,
            "stator_outer_diameter": 200 * Q.mm,
            "back_iron_thickness": 20 * Q.mm,
            "stator_internal_radius": 10 * Q.mm,
            "number_slots": 12 * Q.count,
            "tooth_tip_angle": 0.1 * Q.rad,
        }

        result = geometry_api.get_fscw_stator_geom(**args)

        # Expected payload (without units, as pint wrapper handles conversion)
        expected_payload = {
            "back_iron_thickness": 20.0,
            "number_slots": 12,
            "slot_liner_thickness": 0.5,
            "stator_bore": 100.0,
            "stator_internal_radius": 10.0,
            "stator_outer_diameter": 200.0,
            "tooth_tip_angle": 0.1,
            "tooth_tip_depth": 5.0,
            "tooth_width": 10.0,
            "slot_opening": 3.0,
        }

        mock_post.assert_called_once_with(
            f"{geometry_api.api_url}/stators/fscwseg/", json=expected_payload
        )

        expected_result = {
            "stator_slice": {"name": "Stator Slice"},
            "stator_wedge": {"name": "Stator Wedge"},
        }
        assert result == expected_result


def test_get_fscw_stator_geom_http_error(geometry_api):
    """Test that get_fscw_stator_geom raises an exception on HTTP error."""
    with patch("requests.post") as mock_post:
        mock_post.side_effect = requests.exceptions.RequestException("API Error")

        args = {
            "slot_liner_thickness": 0.5 * Q.mm,
            "stator_bore": 100 * Q.mm,
            "tooth_tip_depth": 5 * Q.mm,
            "slot_opening": 3 * Q.mm,
            "tooth_width": 10 * Q.mm,
            "stator_outer_diameter": 200 * Q.mm,
            "back_iron_thickness": 20 * Q.mm,
            "stator_internal_radius": 10 * Q.mm,
            "number_slots": 12 * Q.count,
            "tooth_tip_angle": 0.1 * Q.rad,
        }

        with pytest.raises(requests.exceptions.RequestException):
            geometry_api.get_fscw_stator_geom(**args)
