import logging
import requests
from ltc_client.api import Quantity
import pint

### Configure Logging
LOGGING_LEVEL = logging.INFO

logger = logging.getLogger()
logger.setLevel(LOGGING_LEVEL)

Q = pint.get_application_registry()


class GeometryApi:
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

    @Q.wraps(
        None, (None, "mm", "mm", "mm", "mm", "mm", "mm", "mm", "mm", "count", "radians")
    )
    def get_fscw_stator_geom(
        self,
        slot_liner_thickness,
        stator_bore,
        tooth_tip_depth,
        slot_opening,
        tooth_width,
        stator_outer_diameter,
        back_iron_thickness,
        stator_internal_radius,
        number_slots,
        tooth_tip_angle,
    ):
        """Get the geometry of a FSCW segmented stator.
        The geometry expects all dimensions in mm and angles in radians, this function is wrapped by Pint to
        ensure consistent units.
        """
        payload = {
            "back_iron_thickness": back_iron_thickness,
            "number_slots": number_slots,
            "slot_liner_thickness": slot_liner_thickness,
            "stator_bore": stator_bore,
            "stator_internal_radius": stator_internal_radius,
            "stator_outer_diameter": stator_outer_diameter,
            "tooth_tip_angle": tooth_tip_angle,
            "tooth_tip_depth": tooth_tip_depth,
            "tooth_width": tooth_width,
            "slot_opening": slot_opening,
        }
        url = f"{self.api_url}/stators/fscwseg/"
        response = requests.post(url, json=payload)
        response.raise_for_status()
        stator_geom = response.json()
        # turn the list of name object pairs back into a dictionary
        geom_dict = {
            g["type"]: {k: v for k, v in g.items() if k != "type"}
            for g in stator_geom["geometry"]["geometries"]
        }
        return geom_dict
