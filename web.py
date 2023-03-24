import jwt
from pathlib import Path
from aiozmq import rpc
from sanic import Sanic, HTTPResponse
from sanic.response import json
from contextlib import asynccontextmanager
from register import routes as register_routes


def rpcservice(bind: str):

    @asynccontextmanager
    async def service():
        client = await rpc.connect_rpc(connect=bind)
        try:
            yield client.call
        finally:
            client.close()

    return service


app = Sanic("Microfarm")
app.blueprint(register_routes)
app.ctx.courrier = rpcservice('tcp://127.0.0.1:5100')
app.ctx.jwt = rpcservice('tcp://127.0.0.1:5200')
app.ctx.accounts = rpcservice('tcp://127.0.0.1:5300')
app.ctx.pki = rpcservice('tcp://127.0.0.1:5400')
app.ctx.websockets = rpcservice('tcp://127.0.0.1:5500')


jwt_public_key = Path('./identities/jwt.pub')
assert jwt_public_key.exists()
with jwt_public_key.open('rb') as fd:
    app.config['jwt_public_key'] = fd.read()
del jwt_public_key


@app.on_request
async def jwt_auth(request):
    namespace, *_ = request.path.lstrip('/').split('/', 1)
    if namespace in ('register', 'login', 'docs'):
        return

    auth = request.headers.get('Authorization')
    if auth is None:
        return HTTPResponse(status=401)

    authtype, token = auth.split(' ', 1)
    if authtype not in ('Bearer', 'JWT'):
        return HTTPResponse(status=403)

    try:
        request.ctx.user = jwt.decode(
            token,
            request.app.config['jwt_public_key'],
            algorithms=["RS256"]
        )
    except jwt.exceptions.InvalidTokenError:
        # generic error, it catches all invalidities
        return HTTPResponse(status=403)


@app.get("/")
async def index(request):
    return json(request.ctx.user)
