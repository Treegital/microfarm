import itertools
import logging
import sys
import zmq

logging.basicConfig(format="%(levelname)s: %(message)s", level=logging.INFO)

REQUEST_TIMEOUT = 20500
SERVER_ENDPOINT = "tcp://localhost:5555"

context = zmq.Context()

logging.info("Connecting to server…")
client = context.socket(zmq.REQ)
client.connect(SERVER_ENDPOINT)


client.send(b'test')
if (client.poll(REQUEST_TIMEOUT) & zmq.POLLIN) != 0:
    reply = client.recv()
    logging.info("Server replied OK (%s)", reply)

client.close()
