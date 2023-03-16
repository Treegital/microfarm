import pika
import yaml
from pathlib import Path


def create_connection(user: str, password: str, host: str):
    credentials = pika.PlainCredentials(user, password)
    parameters = pika.ConnectionParameters(
        host, credentials=credentials
    )
    connection = pika.BlockingConnection(parameters)
    return connection


config = Path(__file__).parent / "topology.yaml"
with config.open('r') as fd:
     topology = yaml.load(fd, Loader=yaml.Loader)

import pdb
pdb.set_trace()