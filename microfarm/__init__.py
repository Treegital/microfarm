from sanic import Sanic, Blueprint
from .rpc import rpcservices
from .listeners import listeners
from .middlewares import jwt_auth
from .register import routes as register_routes
from .certificate import routes as certificate_routes


public_routes = Blueprint.group(register_routes)
secured_routes = Blueprint.group(certificate_routes)
#secured_routes.middleware(jwt_auth, priority=99)


app = Sanic("Microfarm")
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
