import pydantic
from sanic.response import json
from sanic_ext import openapi
from sanic import Blueprint
from .validation import validate_json
from .rpc import RPCResponse


routes = Blueprint("register")


class Registration(pydantic.BaseModel):
    email: pydantic.EmailStr
    name: str
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
@validate_json(Registration)
async def register(request, body: Registration):
    async with request.app.ctx.accounts() as service:
        data = await service.create_account(body.dict())
    response = RPCResponse(**data)
    if response.success:
         async with request.app.ctx.courrier() as service:
             data = await service.send_email(
                 "notifier",
                 [body.email],
                 "Certifarm: registration",
                 f"this is your validation code: {response.data['otp']}"
             )
    return response.json_response()


@routes.post("/register/verify")
@openapi.definition(
    body={'application/json': AccountVerification.schema()},
)
@validate_json(AccountVerification)
async def verify(request, body: AccountVerification):
    async with request.app.ctx.accounts() as service:
        data = await service.verify_account(
            body.email,
            body.token
        )
    return RPCResponse(**data).json_response()


@routes.post("/register/token")
@openapi.definition(
    body={'application/json': TokenRequest.schema()},
)
@validate_json(TokenRequest)
async def request_verification_token(request, body: TokenRequest):
    async with request.app.ctx.accounts() as service:
        data = await service.request_account_token(body.email)
    return RPCResponse(**data).json_response()


@routes.post("/login")
@openapi.definition(
    body={'application/json': Login.schema()},
)
@validate_json(Login)
async def login(request, body: Login):
    async with request.app.ctx.accounts() as service:
        data = await service.verify_credentials(
            body.email,
            body.password
        )
    creds_response = RPCResponse(**data)
    if not creds_response.success:
        return creds_response.json_response()

    async with request.app.ctx.jwt() as service:
        data = await service.get_token(creds_response.data)

    jwt_response = RPCResponse(**data)
    if jwt_response.success:
        jwt_response.metadata['identity'] = creds_response.data

    return jwt_response.json_response()
