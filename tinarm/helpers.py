from . import Quantity, NameQuantityPair
import random
import requests


class Machine(object):
    def __init__(self, stator, rotor, winding):

        self.stator = stator
        self.rotor = rotor
        self.winding = winding

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
        return job

    def run(self):
        pass
