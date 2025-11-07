import logging
import requests
from ltc_client.api import Quantity
import pint

Q = pint.get_application_registry()

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
        terminal_resistance = netlist_params.get("terminal_resistance")
        if not isinstance(terminal_resistance, dict):
            terminal_resistance = Quantity(netlist_params["terminal_resistance"])
            netlist_params["terminal_resistance"] = terminal_resistance.to_dict()
            logger.warning(netlist_params["terminal_resistance"])
        else:
            # Validate that the dictionary has the expected structure
            expected_keys = {"magnitude", "shape", "units"}
            if not expected_keys.issubset(terminal_resistance.keys()):
                raise ValueError(
                    "terminal_resistance dictionary is missing required keys."
                )

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

    def get_circle_packing_max_diameter(self, geom_dict, n=1, part="slot_area"):
        headers = {}
        data_payload = {"geometry": geom_dict[part], "n": n}
        response = requests.request(
            "POST",
            f"{self.api_url}/packing/max_diameter",
            headers=headers,
            json=data_payload,
        )
        response.raise_for_status()
        circle_packing = response.json()
        return circle_packing["max_diameter"] * Q.mm, circle_packing["centers"]

    def get_circle_packing_max_number(
        self,
        geom_dict,
        diameter=1.0 * Q.mm,
        part="slot_area",
    ):
        headers = {}
        data_payload = {"geometry": geom_dict[part], "d": diameter.to("mm").magnitude}
        response = requests.request(
            "POST",
            f"{self.api_url}/packing/max_number",
            headers=headers,
            json=data_payload,
        )
        response.raise_for_status()
        circle_packing = response.json()

        return circle_packing["max_number"], circle_packing["centers"]
