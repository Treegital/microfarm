from sanic import Sanic, Blueprint
from .rpc import rpcservices
from .authentication import authentication, jwt_auth
from .register import routes as register_routes
from .certificate import routes as certificate_routes


public_routes = Blueprint.group(register_routes)
secured_routes = Blueprint.group(certificate_routes)
secured_routes.middleware(jwt_auth, priority=99)


app = Sanic("Microfarm")
app.blueprint(authentication)
app.blueprint(rpcservices)
app.blueprint(public_routes)
app.blueprint(secured_routes)
