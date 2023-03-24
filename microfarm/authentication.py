import jwt
from pathlib import Path
from sanic import Blueprint, HTTPResponse


authentication = Blueprint("auth")


@authentication.listener("before_server_start")
async def setup_jwt_key(app):
    jwt_public_key = Path('./identities/jwt.pub')
    assert jwt_public_key.exists()
    with jwt_public_key.open('rb') as fd:
        app.config['jwt_public_key'] = fd.read()


@authentication.middleware("request", priority=99)
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
