from aiozmq import rpc
from sanic import Sanic
from sanic_ext import validate
from dataclasses import dataclass, asdict
from sanic.response import text, json


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
    def service(self):
        client = await rpc.connect_rpc(connect=bind)
        try:
            yield client.call
        finally:
            client.close()

    return service


app = Sanic("Microfarm")
app.ctx.jwt = service('tcp://127.0.0.1:5556')
app.ctx.pki = service('tcp://127.0.0.1:5556')
app.ctx.courrier = service('tcp://127.0.0.1:5556')
app.ctx.accounts = service('tcp://127.0.0.1:5556')
app.ctx.websockets = service('tcp://127.0.0.1:5556')


@app.post("/account/new")
@validate(json=Registration)
async def register(request, body: Registration):
    with app.ctx.accounts.service() as service:
        response = await service.create_account(asdict(body))
    return json(response)


@app.post("/account/verify")
@validate(json=AccountVerification)
async def verify(request, body: AccountVerification):
    with app.ctx.accounts.service() as service:
        response = await service.verify_account(
            body.email,
            body.token
        )
    return json(response)


@app.post("/account/verify/token")
@validate(json=TokenRequest)
async def request_verification_token(request, body: TokenRequest):
    with app.ctx.accounts.service() as service:
        response = await service.call.request_account_token(body.email)
    return json(response)


@app.post("/login")
@validate(json=Login)
async def login(request, body: Login):
    with app.ctx.accounts.service() as service:
        response = await service.verify_credentials(
            body.email,
            body.password
        )
    return json(response)
