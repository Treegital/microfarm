import peewee
import secrets
import base64
import short_id
from functools import cached_property
from enum import Enum
from datetime import datetime
from cryptography import x509
from cryptography.hazmat.primitives import serialization


dbproxy = peewee.DatabaseProxy()


class EnumField(peewee.CharField):

    def __init__(self, choices, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.choices = choices

    def db_value(self, value):
        if value is None:
            return None
        return value.value

    def python_value(self, value):
        if value is None and self.null:
            return value
        return self.choices(value)


def creation_date():
    return datetime.utcnow()


def uniqueid_factory() -> str:
    unique_id: str = short_id.generate_short_id()
    return unique_id


def salt_generator(size: int):
    def generate_salt():
        return secrets.token_bytes(size)
    return generate_salt


class AccountStatus(str, Enum):
    pending = 'pending'
    active = 'active'
    disabled = 'disabled'


class Account(peewee.Model):

    class Meta:
        database = dbproxy
        table_name = 'accounts'

    id = peewee.CharField(primary_key=True, default=uniqueid_factory)
    email = peewee.CharField(unique=True)
    salter = peewee.BlobField(default=salt_generator(24))
    password = peewee.CharField()
    status = EnumField(AccountStatus, default=AccountStatus.pending)
    creation_date = peewee.DateTimeField(default=creation_date)


class Profile(peewee.Model):

    class Meta:
        database = dbproxy
        table_name = 'profiles'
        indexes = (
            (('rfc4514', 'account'), True),
            (('name', 'account'), True),
        )

    id = peewee.CharField(primary_key=True, default=uniqueid_factory)
    rfc4514 = peewee.CharField()
    name = peewee.CharField(null=True)
    account = peewee.ForeignKeyField(Account)
    creation_date = peewee.DateTimeField(default=creation_date)


class Certificate(peewee.Model):

    class Meta:
        database = dbproxy
        table_name = 'certificates'

    serial_number = peewee.CharField(unique=True, primary_key=True)
    fingerprint = peewee.CharField(unique=True)
    profile = peewee.ForeignKeyField(Profile, backref='certificates')
    account = peewee.ForeignKeyField(Account, backref='certificates')
    pem_cert = peewee.BlobField()
    pem_chain = peewee.BlobField()
    pem_private_key = peewee.BlobField()
    valid_from = peewee.DateTimeField()
    valid_until = peewee.DateTimeField()
    creation_date = peewee.DateTimeField(default=creation_date)
    revocation_date = peewee.DateTimeField(null=True)
    revocation_reason = EnumField(x509.ReasonFlags, null=True)

    @cached_property
    def x509_certificate(self):
        return x509.load_pem_x509_certificate(self.pem_cert)

    def as_bundle(self, password: bytes):
        chain = x509.load_pem_x509_certificates(self.pem_chain)
        private_key = serialization.load_pem_private_key(
            self.pem_private_key, password=password)
        return (self.x509_certificate, private_key, chain)


class RevocationList(peewee.Model):

    class Meta:
        database = dbproxy
        table_name = 'CRLs'

    fingerprint = peewee.CharField(unique=True, primary_key=True)
    der = peewee.BlobField()
    update_date = peewee.DateTimeField(default=creation_date)

    def load(self):
        return x509.load_der_x509_crl(self.der)
