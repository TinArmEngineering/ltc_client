from typing import Dict, Any, List, Optional
import json
import pint

from ltc_client import helpers  # local import to access helpers.decode and logger
from ltc_client.api import NameQuantityPair  # used only for constructing API shapes
import numpy as np

Q = pint.get_application_registry()


class Material:
    """Simple Material representation used by tests.

    Both 'name' and 'reference' are required (tests expect TypeError when missing).
    """

    def __init__(
        self,
        *,
        name: str,
        reference: str,
        key_words: Optional[List[str]] = None,
        material_properties: Optional[Dict[str, Any]] = None,
        id: Optional[str] = None,
    ):
        if name is None or reference is None:
            # keep behavior strict: both required
            raise TypeError("name and reference are required")
        self.name = name
        self.reference = reference
        self.key_words = key_words or []
        self.material_properties = material_properties or {}
        self.id = id

    def to_api(self) -> Dict[str, Any]:
        """Return a dict shaped for the API expected by tests."""
        data = []
        for prop_name, quant in self.material_properties.items():
            # quant is a pint.Quantity
            mag = quant.magnitude
            # normalize into list form
            if hasattr(mag, "tolist"):
                mag_list = list(np.array(mag).ravel())
                shape = list(np.array(mag).shape) if np.array(mag).shape != () else [1]
            else:
                mag_list = [float(mag)]
                shape = [1]
            units = [{"name": str(quant.units), "exponent": 1}]
            data.append(
                {
                    "section": "material_properties",
                    "name": prop_name,
                    "value": {
                        "magnitude": [
                            int(x) if float(x).is_integer() else float(x)
                            for x in mag_list
                        ],
                        "shape": shape,
                        "units": units,
                    },
                }
            )

        return {
            "reference": self.reference,
            "name": self.name,
            "key_words": self.key_words,
            "data": data,
        }

    @classmethod
    def from_api(cls, db_material: Dict[str, Any]) -> "Material":
        """Construct Material from API dict, using helpers.decode for values."""
        material_props: Dict[str, Any] = {}
        for item in db_material.get("data", []):
            if item.get("section") != "material_properties":
                continue
            name = item["name"]
            value = item["value"]
            # decode via helpers.decode so tests that patch helpers.decode/logger work
            dec = helpers.decode(value)
            material_props[name] = dec
        return cls(
            name=db_material["name"],
            reference=db_material.get("reference", ""),
            key_words=db_material.get("key_words", []),
            material_properties=material_props,
            id=db_material.get("id"),
        )
