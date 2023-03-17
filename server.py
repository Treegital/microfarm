import logging
from typing import Tuple
from zero import AsyncZeroClient, ZeroServer
import store
from contextlib import contextmanager


@contextmanager
def auth_rpc():
    client = AsyncZeroClient("localhost", 6000)
    yield client
    client._socket.close()


async def login(msg: Tuple[str, str]) -> dict:
    username, password = msg
    user = await store.get_user_by_username(username)
    if user and user.password == password:
        with auth_rpc() as client:
            jwt = await client.call("get_jwt", username)
        return {
            "jwt": jwt
        }
    else:
        return {"error": "Wrong credentials"}


async def get_user(username: str) -> dict:
    user = await store.get_user_by_username(username)
    if user:
        return user
    else:
        return {"error": "User not found"}


async def create_user(msg: tuple[str, str]) -> dict:
    username, password = msg
    user = await store.create_user(username, password)
    if user:
        return {'result': "user created"}
    else:
        return {"error": "could not create user"}


if __name__ == "__main__":
    app = ZeroServer(port=6001)
    app.register_rpc(login)
    app.register_rpc(get_user)
    app.register_rpc(create_user)
    app.run()