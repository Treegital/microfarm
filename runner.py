import aiozmq.rpc
import asyncio
from minicli import cli, run


@cli
async def jwt():
    client = await aiozmq.rpc.connect_rpc(connect='tcp://127.0.0.1:5555')
    token = await client.call.get_token({"username": "test"})
    ret = await client.call.verify_token(token)
    client.close()


@cli
async def account():
    client = await aiozmq.rpc.connect_rpc(connect='tcp://127.0.0.1:5556')

    response = await client.call.create_account({
        "email": "testtest",
    })
    assert response == {
        'password': ('Missing data for required field.',),
        'email': ('Not a valid email address.',)
    }

    response = await client.call.create_account({
        "email": "test@test.com",
        "password": "toto"
    })
    token = response['otp']

    response = await client.call.verify_account("test@test.com", 'ABC')
    assert response == {'err': 'Invalid token'}

    response = await client.call.request_account_token("test@test.com")
    token = response['otp']

    response = await client.call.verify_account("test@test.com", token)
    assert 'email' in response

    response = await client.call.verify_credentials("test@test.com", "toto")
    assert 'email' in response

    response = await client.call.verify_credentials("test@test.com", "titi")
    assert response == {'err': 'Credentials failed.'}

    client.close()


@cli
async def email():
    client = await aiozmq.rpc.connect_rpc(connect='tcp://127.0.0.1:5557')
    ret = await client.call.send_email(
        'notifier',
        ['toto@gmail.com'],
        'this is my subject',
        'this is my message body, in plain text'
    )
    assert ret is True

    ret = await client.call.send_email(
        'toto',
        ['toto@gmail.com'],
        'this is my subject',
        'this is my message body, in plain text'
    )
    assert ret == {"err": "unknown mailer"}

    client.close()


@cli
async def ws():
    import websockets

    jwt = await aiozmq.rpc.connect_rpc(connect='tcp://127.0.0.1:5555')
    token = await jwt.call.get_token({"email": "test@test.com"})

    uri = "ws://localhost:6001"
    async with websockets.connect(uri) as websocket:
        await websocket.send(token)
        async for message in websocket:
            print(message)

    client.close()


@cli
async def ws_send():
    ws = await aiozmq.rpc.connect_rpc(connect='tcp://127.0.0.1:6000')
    ret = await ws.call.send_message("test@test.com", "this is my message")
    print(ret)
    ret = await ws.call.send_message("couac@test.com", "this is my message")
    print(ret)
    ws.close()


if __name__ == '__main__':
    run()
