import pika
import peewee
import orjson
import threading
import ormsgpack
import models


stopEvent = threading.Event()


def create_connection():
    credentials = pika.PlainCredentials("guest", "guest")
    parameters = pika.ConnectionParameters(
        "localhost", credentials=credentials
    )
    connection = pika.BlockingConnection(parameters)
    return connection


def create_certificate(raw_data):
    data = ormsgpack.unpackb(raw_data)
    print(data)
    return models.Certificate.create(**data)


def revoke_certificate(raw_data):
    data = ormsgpack.unpackb(raw_data)
    return data


METHODS = {
    'persistence.certificate.create': create_certificate,
    'persistence.certificate.revoke': revoke_certificate
}


def persistence_service():

    db = peewee.SqliteDatabase('app.db')
    models.dbproxy.initialize(db)
    with db:
        db.create_tables([
            models.Account,
            models.Profile,
            models.Certificate,
            models.RevocationList
        ])

    connection = create_connection()
    try:
        channel = connection.channel()
        channel.exchange_declare(
            'service.persistence',
            exchange_type='topic',
            durable=False,
            auto_delete=False
        )
        channel.queue_declare(
            queue="persistence.certificate",
            durable=True,
            exclusive=False,
            auto_delete=False
        )
        channel.queue_bind(
            exchange='service.persistence',
            queue="persistence.certificate",
            routing_key="persistence.certificate.*"
        )

        generator = channel.consume("persistence.certificate", inactivity_timeout=2)
        for method_frame, properties, body in generator:
            if (method_frame, properties, body) == (None, None, None):
                # Inactivity : Check for flag
                if stopEvent.is_set():
                    break
            else:
                method = METHODS[method_frame.routing_key]
                try:
                    with db.atomic():
                        result = method(body)
                    print(f'got {result} to persist.')
                except Exception as exc:
                    print(exc)
                    channel.basic_ack(method_frame.delivery_tag)

    finally:
        if connection.is_open:
            connection.close()


if __name__ == '__main__':
    try:
        persistence_service()
    except KeyboardInterrupt:
        stopEvent.set()
