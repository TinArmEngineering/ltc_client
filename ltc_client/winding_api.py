import logging
import requests
### Configure Logging
LOGGING_LEVEL = logging.INFO

logger = logging.getLogger()
logger.setLevel(LOGGING_LEVEL)

class WindingApi:
    """
    The TAE API
    """

    def __init__(self, aux_root_url, api_key=None, org_id=None, node_id=None):
        """
        Initialize the API
        """
        self._root_url = aux_root_url
        self._api_key = api_key
        self._org_id = org_id
        self._node_id = node_id

        logger.info(f"root_url: {self._root_url}")
    
    def create_winding_report(self, winding_params):
        headers = {}
        response = requests.request("POST", f"{self.winding_api_url}/windingreport", headers=headers, json=winding_params)
        response.raise_for_status()
        winding_report = response.text()
        return winding_report
    
    def create_winding(self, winding_params):
        headers = {}
        response = requests.request("POST", f"{self.winding_api_url}/winding", headers=headers, json=winding_params)
        response.raise_for_status()
        winding = response.json()
        return winding
    
    def create_winding_array(self, winding_params):
        headers = {}
        response = requests.request("POST", f"{self.winding_api_url}/winding_array", headers=headers, json=winding_params)
        response.raise_for_status()
        winding_array = response.json()
        return winding_array

