from sanic import Sanic
from .rpc import rpcservices
from .authentication import authentication
from .register import routes as register_routes


app = Sanic("Microfarm")
app.blueprint(authentication)
app.blueprint(rpcservices)
app.blueprint(register_routes)
