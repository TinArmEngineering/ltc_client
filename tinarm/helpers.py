from . import Quantity, NameQuantityPair
import random
import requests


class Machine(object):
    def __init__(self, stator, rotor, winding, materials=None):

        self.stator = stator
        self.rotor = rotor
        self.winding = winding
        if materials is not None:
            self.materials = materials
        else:
            self.materials = {
                "rotor_lamination": "66018e5d1cd3bd0d3453646f",  # default M230-35A
                "rotor_magnet": "66018e5b1cd3bd0d3453646c",  # default is N35UH
                "rotor_air_L": "6602fb42c4a87c305481e8a6",
                "rotor_air_R": "6602fb42c4a87c305481e8a6",
                "rotor_banding": "6602fb42c4a87c305481e8a6",
                "stator_lamination": "66018e5d1cd3bd0d3453646f",  # default M230-35A
                "stator_slot_wedge": "6602fb7239bfdea291a25dd7",
                "stator_slot_liner": "6602fb5166d3c6adaa8ebe8c",
                "stator_slot_winding": "66018e5d1cd3bd0d34536470",
                "stator_slot_potting": "6602fd41b8e866414fe983ec",
            }

    def __repr__(self) -> str:
        return f"Machine({self.stator}, {self.rotor}, {self.winding})"

    def to_api(self):
        stator_api = [
            NameQuantityPair("stator", k, Quantity(*self.stator[k].to_tuple()))
            for k in self.stator
        ]
        rotor_api = [
            NameQuantityPair("rotor", k, Quantity(*self.rotor[k].to_tuple()))
            for k in self.rotor
        ]
        winding_api = [
            NameQuantityPair("winding", k, Quantity(*self.winding[k].to_tuple()))
            for k in self.winding
        ]
        data = []
        data.extend(list(x.to_dict() for x in stator_api))
        data.extend(list(x.to_dict() for x in rotor_api))
        data.extend(list(x.to_dict() for x in winding_api))
        return data


class Job(object):
    def __init__(self, machine: Machine, operating_point, simulation, title=None):
        if title is None:
            self.title = self.generate_title()
        else:
            self.title = title
        self.type = "electromagnetic_spmbrl_fscwseg"
        self.status = 0
        self.machine = machine
        self.operating_point = operating_point
        self.simulation = simulation

    def __repr__(self) -> str:
        return f"Job({self.machine}, {self.operating_point}, {self.simulation})"

    def generate_title(self):
        "gets a random title from the wordlists"
        random_offset = random.randint(500, 286797)
        response = requests.get(
            "https://github.com/taikuukaits/SimpleWordlists/raw/master/Wordlist-Adjectives-All.txt",
            headers={
                "Range": "bytes={1}-{0}".format(random_offset, random_offset - 500),
                "accept-encoding": "identity",
            },
        )
        adjective = random.choice(response.text.splitlines()[1:-1])
        random_offset = random.randint(500, 871742)
        response = requests.get(
            "https://github.com/taikuukaits/SimpleWordlists/raw/master/Wordlist-Nouns-All.txt",
            headers={
                "Range": "bytes={1}-{0}".format(random_offset, random_offset - 500),
                "accept-encoding": "identity",
            },
        )
        noun = random.choice(response.text.splitlines()[1:-1])
        title = f"{adjective}-{noun}"
        return title

    def to_api(self):
        job = {
            "status": 0,
            "title": self.title,
            "type": self.type,
            "tasks": 11,
            "data": [],
            "materials": [],
        }

        operating_point_api = [
            NameQuantityPair(
                "operating_point", k, Quantity(*self.operating_point[k].to_tuple())
            )
            for k in self.operating_point
        ]

        simulation_api = [
            NameQuantityPair("simulation", k, Quantity(*self.simulation[k].to_tuple()))
            for k in self.simulation
        ]

        job["data"].extend(list(x.to_dict() for x in operating_point_api))
        job["data"].extend(list(x.to_dict() for x in simulation_api))
        job["data"].extend(self.machine.to_api())
        job["materials"] = [
            {"part": key, "material_id": value}
            for key, value in self.machine.materials.items()
        ]
        return job

    def run(self):
        pass
