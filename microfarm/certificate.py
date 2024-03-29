import uuid
import pydantic
import typing as t
from sanic.response import json, raw, empty
from sanic_ext import validate, openapi
from sanic import Blueprint
from cryptography import x509
from cryptography.x509 import ocsp, load_pem_x509_certificates
from functools import cached_property
from cryptography.hazmat.primitives import hashes, serialization
from .rpc import RPCUnavailableError
from .validation import validate_json, validation_errors_definition


routes = Blueprint('certificate')


reverse_oid_lookup = {
    v: k for k, v in vars(x509.oid.NameOID).items()
    if not k.startswith('_')
}


class FieldOrdering(pydantic.BaseModel):
    key: str
    order: t.Literal['asc'] | t.Literal['desc']


class CertificatesListing(pydantic.BaseModel):
    offset: t.Optional[int] = 0
    limit: t.Optional[int] = 0
    sort_by: t.List[FieldOrdering] = []


class RevocationRequest(pydantic.BaseModel):
    reason: x509.ReasonFlags


class CertificateRequestResponse(pydantic.BaseModel):
    request: uuid.UUID


class Identity(pydantic.BaseModel):

    class Config:
        allow_mutation = False
        keep_untouched = (cached_property,)

    common_name: str
    email_address : t.Optional[pydantic.EmailStr] = None
    business_category : t.Optional[str] = None
    country_name : t.Optional[str] = None
    dn_qualifier : t.Optional[str] = None
    domain_component : t.Optional[str] = None
    generation_qualifier : t.Optional[str] = None
    given_name : t.Optional[str] = None
    inn : t.Optional[str] = None
    jurisdiction_country_name : t.Optional[str] = None
    jurisdiction_locality_name : t.Optional[str] = None
    jurisdiction_state_or_province_name : t.Optional[str] = None
    locality_name : t.Optional[str] = None
    ogrn : t.Optional[str] = None
    organizational_unit_name : t.Optional[str] = None
    organization_name : t.Optional[str] = None
    postal_address : t.Optional[str] = None
    postal_code : t.Optional[str] = None
    pseudonym : t.Optional[str] = None
    serial_number : t.Optional[str] = None
    snils : t.Optional[str] = None
    state_or_province_name : t.Optional[str] = None
    street_address : t.Optional[str] = None
    surname : t.Optional[str] = None
    title : t.Optional[str] = None
    unstructured_name : t.Optional[str] = None
    user_id : t.Optional[str] = None
    x500_unique_identifier : t.Optional[str] = None

    @cached_property
    def x509_name(self) -> x509.Name:
        return x509.Name([
            x509.NameAttribute(
                getattr(x509.oid.NameOID, name.upper()),
                value
            )
            for name, value in self.dict().items()
            if value is not None
        ])

    @cached_property
    def rfc4514_string(self):
        return self.x509_name.rfc4514_string()

    @classmethod
    def from_rfc4514_string(cls, value: str):
        name = x509.Name.from_rfc4514_string(value)
        values = {
            reverse_oid_lookup[attr.oid].lower(): attr.value
            for attr in name
            if attr.oid in reverse_oid_lookup
        }
        return cls(**values)


@routes.post("/certificates/new")
@openapi.definition(
    secured="token",
    body={'application/json': Identity.schema()},
    response=[
        openapi.definitions.Response(
            {"application/json" : CertificateRequestResponse.schema()},
            status=200
        ),
        openapi.definitions.Response(
            {"application/json" : validation_errors_definition},
            status=422
        ),
        openapi.definitions.Response(
            {"application/json" : RPCUnavailableError.schema()},
            status=503
        )
    ]
)
@validate_json(Identity)
async def new_certificate(request, body: Identity):
    async with request.app.ctx.pki() as service:
        data = await service.generate_certificate(
            request.ctx.user.id,
            body.rfc4514_string
        )
    if data['code'] == 201:
        return json(status=201, body=data['body'])

    raise NotImplementedError(f'Unknown response type: {data}')


@routes.post("/certificates")
@openapi.definition(
    secured="token",
)
@validate_json(CertificatesListing)
async def all_certificates(request, body: CertificatesListing):

    async with request.app.ctx.pki() as service:
        args = body.dict()
        data = await service.list_certificates(
            request.ctx.user.id, **args
        )

    if data['code'] == 200:
        return json(body=data['body'])

    raise NotImplementedError(f'Unknown response type: {data}')


@routes.post("/valid_certificates")
@openapi.definition(
    secured="token",
)
@validate_json(CertificatesListing)
async def valid_certificates(request, body: CertificatesListing):

    async with request.app.ctx.pki() as service:
        args = body.dict()
        data = await service.list_valid_certificates(
            request.ctx.user.id, **args
        )

    if data['code'] == 200:
        return json(body=data['body'])

    raise NotImplementedError(f'Unknown response type: {data}')


@routes.get("/certificates/<serial_number:str>")
@openapi.definition(
    secured="token",
)
async def view_certificate(request, serial_number: str):
    async with request.app.ctx.pki() as service:
        data = await service.get_certificate(
            request.ctx.user.id,
            serial_number
        )

    if data['code'] == 404:
        return empty(status=403)

    if data['code'] == 200:
        return json(body=data['body'])

    raise NotImplementedError(f'Unknown response type: {data}')


@routes.get("/certificates/<serial_number:str>/pem")
@openapi.definition(
    secured="token",
)
async def certificate_pem(request, serial_number: str):
    async with request.app.ctx.pki() as service:
        data = await service.get_certificate_pem(
            request.ctx.user.id, serial_number)

    if data['code'] == 404:
        return empty(status=403)

    elif data['code'] == 200:
        return raw(
            data['body'],
            headers={'Content-Type': 'application/x-pem-file'})

    raise NotImplementedError(f'Unknown response type: {data}')


@routes.get("/certificates/<serial_number:str>/status")
@openapi.definition(
    secured="token",
)
async def certificate_status(request, serial_number: str):
    async with request.app.ctx.pki() as service:
        data = await service.get_certificate_pem(
            request.ctx.user.id, serial_number)

    certs = load_pem_x509_certificates(data['body'])
    builder = ocsp.OCSPRequestBuilder()
    builder = builder.add_certificate(certs[0], certs[1], hashes.SHA256())
    req = builder.build()
    data = req.public_bytes(serialization.Encoding.DER)
    async with request.app.ctx.pki() as service:
        data = await service.certificate_ocsp(data)

    if data['code'] == 404:
        return empty(status=403)

    elif data['code'] == 200:
        return raw(data['body'],
                   headers={'Content-Type': 'application/x-der-file'})

    raise NotImplementedError(f'Unknown response type: {data}')
