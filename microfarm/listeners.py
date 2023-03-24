import jwt
from dataclasses import dataclass
from pathlib import Path
from sanic import Blueprint, HTTPResponse


listeners = Blueprint("listeners")


@listeners.listener("before_server_start")
async def setup_jwt_key(app):
    jwt_public_key = Path('./identities/jwt.pub')
    assert jwt_public_key.exists()
    with jwt_public_key.open('rb') as fd:
        app.config['jwt_public_key'] = fd.read()
