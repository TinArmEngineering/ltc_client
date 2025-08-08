import pytest
import requests
from unittest.mock import Mock, patch
from ltc_client.winding_api import WindingApi


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
