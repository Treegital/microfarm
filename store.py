import peewee
import typing as t
from peewee_aio import Manager

manager = Manager('aiosqlite:///app.db')


class User(manager.Model):
    username = peewee.CharField(primary_key=True)
    password  = peewee.CharField()


async def create_user(username: str, password: str) -> User:
    async with manager:
        async with manager.connection():
            await User.create_table(True)
            test = await User.create(username=username, password=password)
            return test


async def get_user_by_username(username: str) -> t.Optional[User]:
    async with manager:
        async with manager.connection():
            return await User.get_by_id(username)
