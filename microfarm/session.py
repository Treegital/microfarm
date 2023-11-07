from sanic.response import json
from sanic_ext import openapi
from sanic import Blueprint
from sanic.response import json


routes = Blueprint("session")


@routes.get("/info")
@openapi.definition(
    secured="token",
)
async def session_info(request):
    return json(request.ctx.user, status=200)


@routes.get("/refresh")
@openapi.definition(
    secured="token",
)
async def refresh(request):
    async with request.app.ctx.jwt() as service:
        userdata = {**request.ctx.user}
        userdata.pop('exp')  # we remove the expiration date.
        data = await service.get_token(request.ctx.user, delta=20)

    return json(status=200, body=data['body'])
