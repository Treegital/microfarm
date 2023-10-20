import aiozmq.rpc
import asyncio
import hamcrest
from minicli import cli, run


COURRIER = 'tcp://127.0.0.1:5100'
JWT = 'tcp://127.0.0.1:5200'
ACCOUNT = 'tcp://127.0.0.1:5300'
WEBSOCKET = 'tcp://127.0.0.1:5500'
HTTP_WS = 'ws://127.0.0.1:7000'


@cli
async def jwt():
    client = await aiozmq.rpc.connect_rpc(connect=JWT)
    token = await client.call.get_token({"username": "test"})
    ret = await client.call.verify_token(token)
    client.close()


@cli
async def account():
    client = await aiozmq.rpc.connect_rpc(connect=ACCOUNT)

    response = await client.call.clear()
    response = await client.call.create_account({
        "email": "testtest",
    })
    assert response == {
        'code': 400,
        'data': {
            'name': ('Missing data for required field.',),
            'password': ('Missing data for required field.',),
            'email': ('Not a valid email address.',)
        }
    }

    response = await client.call.create_account({
        "email": "test@test.com",
        "name": "Test User",
        "password": "toto"
    })
    hamcrest.assert_that(response, hamcrest.has_entries({
        'code': 201,
        'data': hamcrest.has_entries({
            'otp': hamcrest.instance_of(str)
        })
    }))

    token = response['data']['otp']
    response = await client.call.verify_account("test@test.com", 'ABC')
    assert response == {
        'code': 402,
        'description': 'Invalid token.'
    }

    response = await client.call.request_account_token("test@test.com")
    hamcrest.assert_that(response, hamcrest.has_entries({
        'code': 200,
        'data': hamcrest.has_entries({
            'otp': hamcrest.instance_of(str)
        })
    }))
    token = response['data']['otp']

    response = await client.call.verify_account("test@test.com", token)
    hamcrest.assert_that(response, hamcrest.has_entries({
        'code': 202,
        'data': hamcrest.has_entries({
            'email': 'test@test.com',
            'status': 'active',
            'name': 'Test User',
            'creation_date': hamcrest.instance_of(str),
            'id': hamcrest.instance_of(str)
        })
    }))


    response = await client.call.verify_credentials("test@test.com", "toto")
    hamcrest.assert_that(response, hamcrest.has_entries({
        'code': 202,
        'data': hamcrest.has_entries({
            'email': 'test@test.com',
            'status': 'active',
            'name': 'Test User',
            'creation_date': hamcrest.instance_of(str),
            'id': hamcrest.instance_of(str)
        })
    }))


    response = await client.call.verify_credentials("test@test.com", "titi")
    assert response == {
        'code': 402,
        'description': 'Credentials did not match.'
    }
    client.close()


@cli
async def email():
    client = await aiozmq.rpc.connect_rpc(connect=COURRIER)
    ret = await client.call.send_email(
        'notifier',
        ['toto@gmail.com'],
        'this is my subject',
        'this is my message body, in plain text'
    )
    print(ret)
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

    jwt = await aiozmq.rpc.connect_rpc(connect=JWT)
    token = await jwt.call.get_token({"email": "test@test.com"})

    async with websockets.connect(HTTP_WS) as websocket:
        await websocket.send(token)
        async for message in websocket:
            print(message)

    client.close()


@cli
async def ws_send():
    ws = await aiozmq.rpc.connect_rpc(connect=WEBSOCKET)
    ret = await ws.call.send_message("test@test.com", "this is my message")
    print(ret)
    ret = await ws.call.send_message("couac@test.com", "this is my message")
    print(ret)
    ws.close()


if __name__ == '__main__':
    run()
