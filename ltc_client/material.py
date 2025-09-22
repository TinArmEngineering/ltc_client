from typing import Dict, Any, List, Optional
import json
import pint

from ltc_client import helpers  # local import to access helpers.decode and logger
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
        # import helpers module attributes at call time so tests that patch ltc_client.helpers.NameQuantityPair/Quantity are honored
        helpers_mod = __import__(
            "ltc_client.helpers", fromlist=["NameQuantityPair", "Quantity"]
        )
        NameQuantityPair = helpers_mod.NameQuantityPair
        Quantity = helpers_mod.Quantity
        data = []
        for k in self.material_properties:

            data.append(
                NameQuantityPair(
                    "material_properties",
                    k,
                    Quantity(self.material_properties[k]),
                ).to_dict()
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
