from zero import ZeroClient

zero_client = ZeroClient("localhost", 6001)

def create_user():
    resp = zero_client.call("create_user", ("test", "test"))
    print(resp)


if __name__ == "__main__":
    print(zero_client.call("create_user", ("test", "test")))
    print(zero_client.call("login", ("test", "test")))

