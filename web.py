from aiozmq import rpc
from sanic import Sanic
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


@app.post("/account/new")
@validate(json=Registration)
async def register(request, body: Registration):
    async with app.ctx.accounts() as service:
        response = await service.create_account(asdict(body))
    return json(response)


@app.post("/account/verify")
@validate(json=AccountVerification)
async def verify(request, body: AccountVerification):
    async with app.ctx.accounts() as service:
        response = await service.verify_account(
            body.email,
            body.token
        )
    return json(response)


@app.post("/account/verify/token")
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
