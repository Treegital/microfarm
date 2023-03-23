import jwt
from pathlib import Path
from aiozmq import rpc
from sanic import Sanic, HTTPResponse
from sanic_ext import validate
from dataclasses import dataclass, asdict
from sanic.response import text, json
from contextlib import asynccontextmanager


@dataclass
class Registration:
    email: str
    password: str


@dataclass
class Login:
    email: str
    password: str


@dataclass
class AccountVerification:
    email: str
    token: str


@dataclass
class TokenRequest:
    email: str


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
    if request.path.startswith('/register') or request.path == '/login':
        return

    auth = request.headers.get('Authorization')
    if auth is None:
        return HTTPResponse(status=401)

    authtype, token = auth.split(' ', 1)
    if not authtype in ('Bearer', 'JWT'):
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


@app.post("/register")
@validate(json=Registration)
async def register(request, body: Registration):
    async with app.ctx.accounts() as service:
        response = await service.create_account(asdict(body))
    return json(response)


@app.post("/register/verify")
@validate(json=AccountVerification)
async def verify(request, body: AccountVerification):
    async with app.ctx.accounts() as service:
        response = await service.verify_account(
            body.email,
            body.token
        )
    return json(response)


@app.post("/register/token")
@validate(json=TokenRequest)
async def request_verification_token(request, body: TokenRequest):
    async with app.ctx.accounts() as service:
        response = await service.request_account_token(body.email)
    return json(response)


@app.post("/login")
@validate(json=Login)
async def login(request, body: Login):
    async with app.ctx.accounts() as service:
        response = await service.verify_credentials(
            body.email,
            body.password
        )
    async with app.ctx.jwt() as service:
        response = await service.get_token(response)
    return json(response)


@app.get("/")
async def index(request):
    return json(request.ctx.user)
