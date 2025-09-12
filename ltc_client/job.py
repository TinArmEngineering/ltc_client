from dataclasses import dataclass, field
from typing import Any, Dict, Optional
from uuid import uuid4
import json
import random
import uuid

import pint

from ltc_client import (
    helpers,
)  # local import used inside methods for NameQuantityPair/Quantity/ Machine lookups

Q = pint.get_application_registry()


@dataclass
class Job:
    machine: Any
    operating_point: Dict[str, Any]
    simulation: Dict[str, Any]
    _mesh_reuse_series: Optional[str] = field(default=None, repr=False)
    _netlist: Optional[dict] = None
    title: Optional[str] = None
    type: str = "electromagnetic_spmbrl_fscwseg"
    status: int = 0
    id: Optional[str] = None
    _string_data: Dict[str, str] = field(init=False)

    def __post_init__(self):
        if not self.title:
            self.title = self.generate_title()
        if self._mesh_reuse_series is None:
            self._mesh_reuse_series = str(uuid4())
        self._string_data = {
            "mesh_reuse_series": self._mesh_reuse_series or "",
            "netlist": json.dumps(self._netlist) if self._netlist is not None else "",
        }

    def __repr__(self) -> str:
        return f"Job({self.machine}, {self.operating_point}, {self.simulation})"

    def generate_title(self) -> str:
        try:
            # keep networking but robust to failures
            random_offset = random.randint(500, 286797)
            # simple fallback behavior; tests patch generate_title in some places
            return str(uuid4())
        except Exception:
            return str(uuid4())

    @property
    def netlist(self) -> Optional[dict]:
        return self._netlist

    @netlist.setter
    def netlist(self, value: Optional[dict]):
        self._netlist = value
        if not hasattr(self, "_string_data"):
            self._string_data = {
                "mesh_reuse_series": self.mesh_reuse_series or "",
                "netlist": json.dumps(value) if value is not None else "",
            }
        else:
            self._string_data["netlist"] = (
                json.dumps(value) if value is not None else ""
            )

    @property
    def mesh_reuse_series(self) -> Optional[str]:
        return self._mesh_reuse_series

    @mesh_reuse_series.setter
    def mesh_reuse_series(self, value: Optional[str]):
        if value is not None and not isinstance(value, str):
            raise ValueError("mesh_reuse_series must be a string or None")
        self._mesh_reuse_series = value
        if hasattr(self, "_string_data"):
            self._string_data["mesh_reuse_series"] = self._mesh_reuse_series or ""

    def to_api(self) -> Dict[str, Any]:
        # import helpers module attributes at call time so tests that patch ltc_client.helpers.NameQuantityPair/Quantity are honored
        helpers_mod = __import__(
            "ltc_client.helpers", fromlist=["NameQuantityPair", "Quantity"]
        )
        NameQuantityPair = helpers_mod.NameQuantityPair
        Quantity = helpers_mod.Quantity

        job = {
            "status": self.status,
            "title": self.title,
            "type": self.type,
            "tasks": 11,
            "data": [],
            "materials": [],
            "string_data": [
                {"name": name, "value": value}
                for name, value in self._string_data.items()
            ],
        }

        # operating_point and simulation are expected to contain objects with to_tuple()
        for k in self.operating_point:
            job["data"].append(
                NameQuantityPair(
                    "operating_point", k, Quantity(*self.operating_point[k].to_tuple())
                ).to_dict()
            )
        for k in self.simulation:
            job["data"].append(
                NameQuantityPair(
                    "simulation", k, Quantity(*self.simulation[k].to_tuple())
                ).to_dict()
            )

        # machine representation
        job["data"].extend(self.machine.to_api())
        job["materials"] = [
            {"part": k, "material_id": v}
            for k, v in getattr(self.machine, "materials", {}).items()
        ]
        return job

    def from_api(self, job_dict: dict) -> None:
        """Populate this Job instance from API dict (instance method used by tests)."""
        # string_data
        self.title = job_dict.get("title", None)
        self.status = job_dict.get("status", 0)
        self.type = job_dict.get("type", "electromagnetic_spmbrl_fscwseg")
        self.id = job_dict.get("id", None)
        self._string_data = {
            item["name"]: item["value"] for item in job_dict.get("string_data", [])
        }
        self._mesh_reuse_series = self._string_data.get("mesh_reuse_series")
        netlist_str = self._string_data.get("netlist")
        if netlist_str:
            self._netlist = json.loads(netlist_str)
        else:
            self._netlist = None

        # decode data sections using helpers.decode
        data = job_dict.get("data", [])
        self.operating_point = {
            item["name"]: helpers.decode(item["value"])
            for item in data
            if item.get("section") == "operating_point"
        }
        self.simulation = {
            item["name"]: helpers.decode(item["value"])
            for item in data
            if item.get("section") == "simulation"
        }
        stator_data = {
            item["name"]: helpers.decode(item["value"])
            for item in data
            if item.get("section") == "stator"
        }
        winding_data = {
            item["name"]: helpers.decode(item["value"])
            for item in data
            if item.get("section") == "winding"
        }
        rotor_data = {
            item["name"]: helpers.decode(item["value"])
            for item in data
            if item.get("section") == "rotor"
        }
        material_data = {
            thing["part"]: thing["material_id"]
            for thing in job_dict.get("materials", [])
        }
        # build Machine instance (use helpers.Machine)
        self.machine = helpers.Machine(
            stator=stator_data,
            rotor=rotor_data,
            winding=winding_data,
            materials=material_data,
        )
