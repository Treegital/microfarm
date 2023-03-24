import pydantic
from sanic.response import json
from sanic_ext import validate, openapi
from sanic import Blueprint


routes = Blueprint("register")


class Registration(pydantic.BaseModel):
    email: pydantic.EmailStr
    password: str


class Login(pydantic.BaseModel):
    email: pydantic.EmailStr
    password: str


class AccountVerification(pydantic.BaseModel):
    email: pydantic.EmailStr
    token: str


class TokenRequest(pydantic.BaseModel):
    email: pydantic.EmailStr


@routes.post("/register")
@openapi.definition(
    body={'application/json': Registration.schema()},
)
@validate(json=Registration)
async def register(request, body: Registration):
    async with request.app.ctx.accounts() as service:
        response = await service.create_account(body.dict())
    return json(response)


@routes.post("/register/verify")
@openapi.definition(
    body={'application/json': AccountVerification.schema()},
)
@validate(json=AccountVerification)
async def verify(request, body: AccountVerification):
    async with request.app.ctx.accounts() as service:
        response = await service.verify_account(
            body.email,
            body.token
        )
    return json(response)


@routes.post("/register/token")
@openapi.definition(
    body={'application/json': TokenRequest.schema()},
)
@validate(json=TokenRequest)
async def request_verification_token(request, body: TokenRequest):
    async with request.app.ctx.accounts() as service:
        response = await service.request_account_token(body.email)
    return json(response)


@routes.post("/login")
@openapi.definition(
    body={'application/json': Login.schema()},
)
@validate(json=Login)
async def login(request, body: Login):
    async with request.app.ctx.accounts() as service:
        response = await service.verify_credentials(
            body.email,
            body.password
        )
    async with request.app.ctx.jwt() as service:
        response = await service.get_token(response)
    return json(response)
