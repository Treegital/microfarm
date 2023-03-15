import pika


credentials = pika.PlainCredentials("guest", "guest")
parameters = pika.ConnectionParameters(
    "localhost", credentials=credentials
)
connection = pika.BlockingConnection(parameters)


channel = connection.channel()


channel.exchange_declare(
    'service.mailing',
    exchange_type='topic',
    durable=False,
    auto_delete=False
)

channel.queue_declare(
    queue="mailing",
    durable=True,
    exclusive=False,
    auto_delete=False
)

channel.queue_bind(
    exchange='service.mailing',
    queue="mailing",
    routing_key="mailing.*"
)

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

channel.exchange_declare(
    'service.pki',
    exchange_type='topic',
    durable=False,
    auto_delete=False
)

channel.queue_declare(
    queue="pki.certificate",
    durable=True,
    exclusive=False,
    auto_delete=False
)

channel.queue_bind(
    exchange='service.pki',
    queue="pki.certificate",
    routing_key="pki.certificate.create"
)

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
    routing_key="persistence.certificate.create"
)
