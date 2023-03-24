import asyncio
from aiozmq import rpc
from sanic import Blueprint
from sanic.exceptions import SanicException
from contextlib import asynccontextmanager


rpcservices = Blueprint('rpcservices')


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
