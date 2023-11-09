import orjson
from minio import Minio
from sanic import Sanic, Blueprint
from sanic_ext import Extend
from .rpc import rpcservices
from .storage import storage
from .listeners import listeners
from .middlewares import jwt_auth
from .register import routes as register_routes
from .session import routes as session_routes
from .certificate import routes as certificate_routes


public_routes = Blueprint.group(
    register_routes
)
secured_routes = Blueprint.group(
    session_routes, certificate_routes, storage
)
secured_routes.middleware(jwt_auth, priority=99)


app = Sanic("Microfarm", dumps=orjson.dumps)
app.config.CORS_ORIGINS = "*"
app.config.CORS_ALLOW_HEADERS = [
    'Authorization', 'Content-Type'
]
app.config.MINIO = {
    "endpoint": "localhost:9000",
    "secure": False,
    "access_key": "certifarm",
    "secret_key": "mN}Y*tx95AYN?cj"
}
Extend(app)

app.blueprint(listeners)
app.blueprint(rpcservices)
app.blueprint(public_routes)
app.blueprint(secured_routes)

app.ext.openapi.add_security_scheme(
    "token",
    "http",
    scheme="bearer",
    bearer_format="JWT",
)
