import logging
import orjson
import ormsgpack
import pika
import threading
import time
from pki import create_pki
from bundle import PKI
from cryptography.hazmat.primitives import serialization
from cryptography import x509
from security import generate_password


stopEvent = threading.Event()


def create_connection():
    credentials = pika.PlainCredentials("guest", "guest")
    parameters = pika.ConnectionParameters(
        "localhost", credentials=credentials
    )
    connection = pika.BlockingConnection(parameters)
    return connection


def certificate_subservice(pki: PKI):
    connection = create_connection()
    try:
        ch_input = connection.channel()
        ch_output = connection.channel()
        ch_input.exchange_declare(
            'service.pki',
            exchange_type='topic',
            durable=False,
            auto_delete=False
        )
        ch_input.queue_declare(
            queue="pki.certificate",
            durable=True,
            exclusive=False,
            auto_delete=False
        )
        ch_input.queue_bind(
            exchange='service.pki',
            queue="pki.certificate",
            routing_key="pki.certificate.create"
        )

        ch_output.exchange_declare(
            'service.persistence',
            exchange_type='topic',
            durable=False,
            auto_delete=False
        )
        ch_output.queue_declare(
            queue="persistence.certificate",
            durable=True,
            exclusive=False,
            auto_delete=False
        )
        ch_output.queue_bind(
            exchange='service.persistence',
            queue="persistence.certificate",
            routing_key="persistence.certificate.create"
        )

        generator = ch_input.consume("pki.certificate", inactivity_timeout=2)
        for method_frame, properties, body in generator:
            if (method_frame, properties, body) == (None, None, None):
                # Inactivity : Check for flag
                if stopEvent.is_set():
                    break
            else:
                data = orjson.loads(body)
                print(f'generating certificate {data}')
                subject = x509.Name.from_rfc4514_string(data['identity'])
                bundle = pki.create_bundle(subject)
                password = bytes(generate_password(12), 'ascii')
                result = {
                    'profile': data['profile'],
                    'account': data['user'],
                    'serial_number': str(bundle.certificate.serial_number),
                    'fingerprint': bundle.fingerprint,
                    'pem_cert': bundle.pem_cert,
                    'pem_chain': bundle.pem_chain,
                    'pem_private_key': bundle.dump_private_key(password),
                    'valid_from': bundle.certificate.not_valid_before,
                    'valid_until': bundle.certificate.not_valid_after
                }
                ch_output.basic_publish(
                    exchange='service.persistence',
                    routing_key='persistence.certificate.create',
                    body=ormsgpack.packb(result),
                    properties=pika.BasicProperties(
                        content_type='application/json',
                        delivery_mode=pika.DeliveryMode.Transient)
                )
                ch_input.basic_ack(method_frame.delivery_tag)
    finally:
        if connection.is_open:
            connection.close()


if __name__ == '__main__':
    pki = create_pki()
    cert_service = threading.Thread(
        target=certificate_subservice,
        args=[pki]
    )
    cert_service.start()

    try:
        stopEvent.wait()
    except KeyboardInterrupt:
        stopEvent.set()
    finally:
        cert_service.join()
