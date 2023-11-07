"""
RPC Services
------------

return codes:

  100-199 -> Informational content
  200-299 -> Success
  300-399 -> Further action is needed
  400-499 -> Input error (erroneous data received)
  500-599 -> Output error (an error occured while processing the data)
  600-699 -> Database-related error
"""

import asyncio
import pydantic
import typing as t
from aiozmq import rpc
from sanic import Blueprint
from sanic.response import json
from sanic.exceptions import SanicException
from contextlib import asynccontextmanager


rpcservices = Blueprint('rpcservices')


class RPCUnavailableError(pydantic.BaseModel):
    status: int
    message: str
    description: str


def rpcservice(name: str, bind: str):

    @asynccontextmanager
    async def service():
        try:
            client = await rpc.connect_rpc(connect=bind, timeout=0.5)
            try:
                yield client.call
            finally:
                client.close()
        except asyncio.TimeoutError:
            # log
            raise SanicException(
                f"Service `{name}` is unavailable.", status_code=503)

    return service


@rpcservices.listener("before_server_start")
async def setup_rpc(app):
    app.ctx.courrier = rpcservice('courrier', 'tcp://127.0.0.1:5100')
    app.ctx.jwt = rpcservice('jwt', 'tcp://127.0.0.1:5200')
    app.ctx.accounts = rpcservice('accounts', 'tcp://127.0.0.1:5300')
    app.ctx.pki = rpcservice('PKI', 'tcp://127.0.0.1:5400')
    app.ctx.websockets = rpcservice('websockets', 'tcp://127.0.0.1:5500')
