import jwt
import typing as t
from sanic import HTTPResponse


class User(dict):
    id: str
    exp: int
    email: str
    name: str

    @property
    def id(self) -> str:
        return self['id']

    @property
    def name(self) -> str:
        return self['name']

    @property
    def email(self) -> str:
        return self['email']

    @property
    def exp(self) -> int:
        return self['exp']


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
        request.ctx.user = User(userdata)
    except jwt.exceptions.InvalidTokenError:
        # generic error, it catches all invalidities
        return HTTPResponse(status=403)
