import pika
import yaml
from pathlib import Path
from minicli import cli, run


def create_connection(*, user: str, password: str, host: str):
    credentials = pika.PlainCredentials(user, password)
    parameters = pika.ConnectionParameters(
        host, credentials=credentials
    )
    connection = pika.BlockingConnection(parameters)
    return connection


def ensure_topology(project: dict):
    connection = create_connection(**project['credentials'])
    with connection as conn:
        channel = connection.channel()
        topology = project['topology']
        for name, queue_conf in topology['queues'].items():
            channel.queue_declare(
                name,
                **queue_conf
            )
        for name, exchange_conf in topology['exchanges'].items():
            channel.exchange_declare(
                name,
                **exchange_conf
            )
        for binding in topology['bindings']:
            channel.queue_bind(**binding)


@cli
def create(config: Path):
    with config.open('r') as fd:
        topology = yaml.load(fd, Loader=yaml.Loader)
    ensure_topology(topology)


if __name__ == '__main__':
    run()
