import logging
import requests
from ltc_client.api import Quantity

### Configure Logging
LOGGING_LEVEL = logging.INFO

logger = logging.getLogger()
logger.setLevel(LOGGING_LEVEL)


class WindingApi:
    """
    The TAE API
    """

    def __init__(self, api_url, api_key=None, org_id=None, node_id=None):
        """
        Initialize the API
        """
        self.api_url = api_url
        self._api_key = api_key
        self._org_id = org_id
        self._node_id = node_id

        logger.info(f"api_url: {self.api_url}")

    def create_winding_report(self, winding_params):
        headers = {}
        response = requests.request(
            "POST",
            f"{self.api_url}/windingreport",
            headers=headers,
            json=winding_params,
        )
        response.raise_for_status()
        winding_report = response.text
        return winding_report

    def create_winding(self, winding_params):
        headers = {}
        response = requests.request(
            "POST", f"{self.api_url}/winding", headers=headers, json=winding_params
        )
        response.raise_for_status()
        winding = response.json()
        return winding

    def create_winding_array(self, winding_params):
        headers = {}
        response = requests.request(
            "POST",
            f"{self.api_url}/winding_array",
            headers=headers,
            json=winding_params,
        )
        response.raise_for_status()
        winding_array = response.json()
        return winding_array

    def create_winding_netlist(self, netlist_params):
        """netlist_params =
                {
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
                "magnitude": [
                0.1,10, 2000
                ],
                "shape": [3
                ],
                "units": [
                {
                    "name": "ohm",
                    "exponent": 1
                }
                ],
                "unit_string": "Ω"
            }
        }
        """
        if isinstance(netlist_params["terminal_resistance"], dict):
            all_ok = True
            for expectedkey in ["magnitude", "shape", "units"]:
                if expectedkey not in netlist_params["terminal_resistance"]:
                    all_ok = False
            if not all_ok:
                raise (ValueError, "terminal_resistance is not correct")
        else:
            terminal_resistance = Quantity(netlist_params["terminal_resistance"])
            netlist_params["terminal_resistance"] = terminal_resistance.to_dict()
            logger.warning(netlist_params["terminal_resistance"])
        headers = {}
        response = requests.request(
            "POST",
            f"{self.api_url}/winding_netlist",
            headers=headers,
            json=netlist_params,
        )
        response.raise_for_status()
        winding_netlist = response.json()
        return winding_netlist
