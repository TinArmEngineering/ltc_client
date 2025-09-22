from dataclasses import dataclass, field
from typing import Any, Dict, Optional
from uuid import uuid4
import json
import random
import uuid

import pint

Q = pint.get_application_registry()


@dataclass
class Job:
    machine: Any
    operating_point: Dict[str, Any]
    simulation: Dict[str, Any]
    title: Optional[str] = None
    type: str = "electromagnetic_spmbrl_fscwseg"
    status: int = 0
    id: Optional[str] = None

    # Private attributes that are set in __post_init__
    _mesh_reuse_series: Optional[str] = field(init=False, repr=False)
    _netlist: Optional[dict] = field(init=False)
    _string_data: Dict[str, str] = field(init=False, repr=False)

    def __init__(
        self,
        machine: Any,
        operating_point: Dict[str, Any],
        simulation: Dict[str, Any],
        title: Optional[str] = None,
        type: str = "electromagnetic_spmbrl_fscwseg",
        status: int = 0,
        id: Optional[str] = None,
        mesh_reuse_series: Optional[str] = None,
        netlist: Optional[dict] = None,
    ):
        # Manually call the dataclass-generated init for standard fields
        self.machine = machine
        self.operating_point = operating_point
        self.simulation = simulation
        self.title = title
        self.type = type
        self.status = status
        self.id = id

        # --- Post-init logic ---
        if not self.title:
            self.title = self.generate_title()

        if mesh_reuse_series is not None and not isinstance(mesh_reuse_series, str):
            raise ValueError("mesh_reuse_series must be a string or None")
        self._mesh_reuse_series = (
            mesh_reuse_series if mesh_reuse_series is not None else str(uuid4())
        )

        if netlist is not None and not isinstance(netlist, dict):
            raise ValueError("netlist must be a dict or None")
        self._netlist = netlist

        self._string_data = {
            "mesh_reuse_series": self._mesh_reuse_series or "",
            "netlist": json.dumps(self._netlist) if self._netlist is not None else "",
        }

    def __repr__(self) -> str:
        return f"Job({self.machine}, {self.operating_point}, {self.simulation})"

    def generate_title(self) -> str:
        return str(uuid4())

    @property
    def netlist(self) -> Optional[dict]:
        return self._netlist

    @netlist.setter
    def netlist(self, value: Optional[dict]):
        if value is not None and not isinstance(value, dict):
            raise ValueError("netlist must be a dict or None")
        self._netlist = value
        if hasattr(self, "_string_data"):
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

    @classmethod
    def from_api(cls, job_dict: dict) -> "Job":
        """Create a Job instance from an API dict."""
        # local import to avoid circular dependency
        from ltc_client import helpers

        # string_data
        title = job_dict.get("title", None)
        status = job_dict.get("status", 0)
        job_type = job_dict.get("type", "electromagnetic_spmbrl_fscwseg")
        job_id = job_dict.get("id", None)
        string_data = {
            item["name"]: item["value"] for item in job_dict.get("string_data", [])
        }
        mesh_reuse_series = string_data.get("mesh_reuse_series")
        netlist_str = string_data.get("netlist")
        if netlist_str:
            netlist = json.loads(netlist_str)
        else:
            netlist = None

        # decode data sections using helpers.decode
        data = job_dict.get("data", [])
        operating_point = {
            item["name"]: helpers.decode(item["value"])
            for item in data
            if item.get("section") == "operating_point"
        }
        simulation = {
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
        machine = helpers.Machine(
            stator=stator_data,
            rotor=rotor_data,
            winding=winding_data,
            materials=material_data,
        )
        return cls(
            machine=machine,
            operating_point=operating_point,
            simulation=simulation,
            title=title,
            type=job_type,
            status=status,
            id=job_id,
            mesh_reuse_series=mesh_reuse_series,
            netlist=netlist,
        )
