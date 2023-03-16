import pika
import binascii
import hashlib
import secrets
import pika.exceptions
from microfarm.messaging import CreateAccount


credentials = pika.PlainCredentials('guest', 'guest')
parameters = pika.ConnectionParameters(
    'localhost',
    credentials=credentials
)
connection = pika.BlockingConnection(parameters)
channel = connection.channel()


def hash_password(password: str) -> str:
    """Hash a password for storing."""
    salt = hashlib.sha256(
        secrets.token_bytes(60)
    ).hexdigest().encode('ascii')
    pwdhash = hashlib.pbkdf2_hmac(
        'sha512',
        password.encode('utf-8'),
        salt,
        100000
    )
    pwdhash = binascii.hexlify(pwdhash)
    return salt + pwdhash


registration = CreateAccount(
    email="test@example.com",
    password=hash_password("test")
)


# Send a message
channel.basic_publish(
    exchange='service.persistence',
    routing_key='persistence.account.create',
    body=registration.SerializeToString(),
    properties=pika.BasicProperties(
        content_type='application/x-protobuf',
        delivery_mode=pika.DeliveryMode.Transient)
)
