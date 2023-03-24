import jwt
import typing as t
from dataclasses import dataclass
from sanic import HTTPResponse


@dataclass
class User:
    id: str
    email: str
    metadata: dict


async def jwt_auth(request) -> t.Optional[HTTPResponse]:
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
