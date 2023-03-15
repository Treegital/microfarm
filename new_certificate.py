import pika
import pika.exceptions
import orjson


credentials = pika.PlainCredentials('guest', 'guest')
parameters = pika.ConnectionParameters(
    'localhost',
    credentials=credentials
)
connection = pika.BlockingConnection(parameters)
channel = connection.channel()


certificate_demand = orjson.dumps({
    'user': 'test',
    'profile': 'profile_id',
    'identity': ("ST=Florida,O=IBM,OU=Marketing,L=Tampa,"
                 "1.2.840.113549.1.9.1=johndoe@example.com,"
                 "C=US,CN=John Doe")
})


# Send a message
channel.basic_publish(
    exchange='service.pki',
    routing_key='pki.certificate.create',
    body=certificate_demand,
    properties=pika.BasicProperties(
        content_type='application/json',
        delivery_mode=pika.DeliveryMode.Transient)
)
