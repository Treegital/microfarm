import pydantic
from sanic.response import json, raw, empty
from sanic_ext import openapi
from sanic import Blueprint
from sanic.exceptions import SanicException
from .validation import validate_json


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

    if data['code'] == 409:
        # Conflict.
        # Some fields conflict with current database records
        return json(data['body'], status=409)

    if data['code'] == 400:
        # Invalid request.
        return json(data['body'], status=400)

    if data['code'] == 601:
        # A database error occured.
        return json(data['body'], status=500)

    if data['code'] == 201:
        try:
            async with request.app.ctx.courrier() as service:
                data = await service.send_email(
                    "notifier",
                    [body.email],
                    "Certifarm: registration",
                    f"this is your validation code: {data['body']}"
                )
        except SanicException:
            # Couldn't send an email
            return empty(status=206)
        else:
            if data['code'] == 200:
                # Email was enqueued.
                return empty(status=201)

    raise NotImplementedError(
        f"An unknown response code was returned : {data['code']}")



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
    if data['code'] == 401:
        return json({
            "email": "This account does not exist or is already verified."
        }, status=400)

    if data['code'] == 402:
        return json({
            "token": "The token is invalid or expired."
        }, status=400)

    if data['code'] == 202:
        return empty(status=200)

    raise NotImplemented('Unknow return code.')


@routes.post("/register/token")
@openapi.definition(
    body={'application/json': TokenRequest.schema()},
)
@validate_json(TokenRequest)
async def request_verification_token(request, body: TokenRequest):
    async with request.app.ctx.accounts() as service:
        data = await service.request_account_token(body.email)

    if data['code'] == 200:
        async with request.app.ctx.courrier() as service:
            result = await service.send_email(
                "notifier",
                [body.email],
                "Certifarm: registration [requested]",
                f"this is your new validation code: {data['body']}"
            )
            if result['code'] == 200:
                # Email enqueued.
                return empty(status=202)
            return raw(
                status=500,
                body=(
                    "The service was unable to send a new code. "
                    "Please try again later."
                )
            )

    if data['code'] == 401:
        # the account does not exist.
        pass

    # Pokerface. Maybe it was done, maybe it wasn't.
    return empty(status=202)


@routes.post("/login")
@openapi.definition(
    body={'application/json': Login.schema()},
)
@validate_json(Login)
async def login(request, body: Login):
    async with request.app.ctx.accounts() as service:
        login_response = await service.verify_credentials(
            body.email,
            body.password
        )
    if login_response['code'] == 402:
        # Credentials do not match
        return empty(status=401)

    elif login_response['code'] == 401:
        # Account do not exist.
        # Poker faced.
        return empty(status=401)

    elif login_response['code'] == 202:
        # AccountInfo is returned
        account_info = login_response['body']
        async with request.app.ctx.jwt() as service:
            jwt_response = await service.get_token(account_info, delta=20)

        if jwt_response['code'] == 200:
            return raw(body=jwt_response['body'])

        raise NotImplementedError(
            f'Unknown response from JWT : {jwt_response}')

    raise NotImplementedError(
        f'Unknown response from Account : {login_response}')
