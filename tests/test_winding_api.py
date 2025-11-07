import pytest
import requests
from unittest.mock import Mock, patch
from ltc_client.winding_api import WindingApi
import pint

Q = pint.get_application_registry()


@pytest.fixture
def winding_api():
    return WindingApi("http://test-url")


@pytest.fixture
def mock_response():
    mock = Mock()
    mock.raise_for_status = Mock()
    return mock


def test_create_winding_report(winding_api, mock_response):
    with patch("requests.request", return_value=mock_response) as mock_request:
        mock_response.text = "test report"
        params = {"param": "value"}

        result = winding_api.create_winding_report(params)

        mock_request.assert_called_once_with(
            "POST", f"{winding_api.api_url}/windingreport", headers={}, json=params
        )
        assert result == "test report"


def test_create_winding(winding_api, mock_response):
    with patch("requests.request", return_value=mock_response) as mock_request:
        mock_response.json = Mock(return_value={"id": 1})
        params = {"param": "value"}

        result = winding_api.create_winding(params)

        mock_request.assert_called_once_with(
            "POST", f"{winding_api.api_url}/winding", headers={}, json=params
        )
        assert result == {"id": 1}


def test_create_winding_array(winding_api, mock_response):
    with patch("requests.request", return_value=mock_response) as mock_request:
        mock_response.json = Mock(return_value=[{"id": 1}])
        params = {"param": "value"}

        result = winding_api.create_winding_array(params)

        mock_request.assert_called_once_with(
            "POST", f"{winding_api.api_url}/winding_array", headers={}, json=params
        )
        assert result == [{"id": 1}]


def test_create_winding_netlist(winding_api, mock_response):
    with patch("requests.request", return_value=mock_response) as mock_request:
        mock_response.json = Mock(return_value=[{"id": 1}])
        netlist_params = {
            "number_slots": 12,
            "number_phases": 3,
            "number_layers": 2,
            "coil_span": 1,
            "turns_per_coil": 25,
            "empty_slots": 0,
            "number_poles": 10,
            "symmetry": 2,
            "fill_factor": 61.68048403644881,
            "terminal_resistance": {
                "magnitude": [0.1, 10, 2000],
                "shape": [3],
                "units": [{"name": "ohm", "exponent": 1}],
                "unit_string": "Ω",
            },
        }

        result = winding_api.create_winding_netlist(netlist_params)

        mock_request.assert_called_once_with(
            "POST",
            f"{winding_api.api_url}/winding_netlist",
            headers={},
            json=netlist_params,
        )
        assert result == [{"id": 1}]


def test_create_winding_netlist_convert_quantity(winding_api, mock_response):
    import pint

    Q = pint.get_application_registry()
    with patch("requests.request", return_value=mock_response) as mock_request:
        mock_response.json = Mock(return_value=[{"id": 1}])
        netlist_params = {"terminal_resistance": 10 * Q.uohm}

        netlist_params_converted = {
            "terminal_resistance": {
                "magnitude": [10],
                "shape": [1],
                "units": [{"name": "microohm", "exponent": 1}],
            }
        }

        result = winding_api.create_winding_netlist(netlist_params)

        mock_request.assert_called_once_with(
            "POST",
            f"{winding_api.api_url}/winding_netlist",
            headers={},
            json=netlist_params_converted,
        )
        assert result == [{"id": 1}]


def test_api_request_error(winding_api):
    with patch("requests.request") as mock_request:
        mock_request.side_effect = requests.exceptions.RequestException

        with pytest.raises(requests.exceptions.RequestException):
            winding_api.create_winding({"param": "value"})


def test_get_circle_packing_max_diameter(winding_api, mock_response):
    """Test get_circle_packing_max_diameter successfully returns diameter and centers."""
    with patch("requests.request", return_value=mock_response) as mock_request:
        mock_response.json.return_value = {
            "centers": [[31.67, -2.44], [35.86, -3.38]],
            "max_diameter": 4.28,
        }

        geom_dict = {
            "slot_area": {
                # Simplified points list containing only referenced vertices
                "points": [
                    [26.032597975719533, 0],  # old index 18
                    [38.19882197136452, -0.3],  # old index 19
                    [37.75306092902646, -5.826353103719018],  # old index 20
                    [37.254213301257415, -6.151714501211407],  # old index 21
                    [27.12185524186896, -3.4367573417752926],  # old index 22
                    [26.849505811595606, -3.187195068589932],  # old index 23
                    [26.332597975719533, -1.767002461581272],  # old index 24
                    [26.332597975719533, -0.3],  # old index 25
                ],
                # Re-indexed path
                "path": [
                    [
                        [7, 6, -1],
                        [6, 5, -1],
                        [5, 4, -1],
                        [4, 3, -1],
                        [3, 2, -1],
                        [2, 1, -1],
                        [1, 0, -1],
                        [0, 7, -1],
                    ]
                ],
                "svg_path": "",
                "units": "mm",
                "classes": "winding conductor_0",
                "construction_circles": [],
                "neighbouring_part_hint": [],
                "area": 51.99102437460619,
            }
        }

        n = 25

        diameter, centers = winding_api.get_circle_packing_max_diameter(geom_dict, n)

        expected_payload = {"geometry": geom_dict["slot_area"], "n": n}
        mock_request.assert_called_once_with(
            "POST",
            f"{winding_api.api_url}/packing/max_diameter",
            headers={},
            json=expected_payload,
        )

        assert diameter == 4.28 * Q.mm
        assert centers == [[31.67, -2.44], [35.86, -3.38]]


def test_get_circle_packing_max_number(winding_api, mock_response):
    """Test get_circle_packing_max_number successfully returns number and centers."""
    with patch("requests.request", return_value=mock_response) as mock_request:
        mock_response.json.return_value = {
            "max_number": 5,
            "centers": [[0.1, 0.2], [0.3, 0.4], [0.5, 0.6], [0.7, 0.8], [0.9, 1.0]],
        }

        geom_dict = {"slot_area": {"shape": "circle", "radius": 10}}
        diameter_to_pack = 1.5 * Q.mm

        max_number, centers = winding_api.get_circle_packing_max_number(
            geom_dict, diameter=diameter_to_pack
        )

        expected_payload = {
            "geometry": geom_dict["slot_area"],
            "d": diameter_to_pack.to("mm").magnitude,
        }
        mock_request.assert_called_once_with(
            "POST",
            f"{winding_api.api_url}/packing/max_number",
            headers={},
            json=expected_payload,
        )

        assert max_number == 5
        assert len(centers) == 5
