import jwt
from dataclasses import dataclass
from pathlib import Path
from sanic import Blueprint, HTTPResponse


authentication = Blueprint("auth")


@dataclass
class User:
    id: str
    email: str
    metadata: dict


@authentication.listener("before_server_start")
async def setup_jwt_key(app):
    jwt_public_key = Path('./identities/jwt.pub')
    assert jwt_public_key.exists()
    with jwt_public_key.open('rb') as fd:
        app.config['jwt_public_key'] = fd.read()


async def jwt_auth(request):
    auth = request.headers.get('Authorization')
    if auth is None:
        return HTTPResponse(status=401)

    authtype, token = auth.split(' ', 1)
    if authtype not in ('Bearer', 'JWT'):
        return HTTPResponse(status=403)

    try:
        userdata = jwt.decode(
            token,
            request.app.config['jwt_public_key'],
            algorithms=["RS256"]
        )
        request.ctx.user = User(
            id=userdata['id'],
            email=userdata['email'],
            metadata=userdata
        )
    except jwt.exceptions.InvalidTokenError:
        # generic error, it catches all invalidities
        return HTTPResponse(status=403)
