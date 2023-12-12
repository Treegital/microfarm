import io
import toml
import uuid
import pydantic
import minio
import pathlib
import typing as t
import dateutil.parser
import asyncio
import aiohttp
from datetime import timedelta
from base64 import b64encode
from urllib.parse import unquote
from sanic.response import json, raw, empty
from sanic_ext import openapi, cors
from sanic import Blueprint
from .validation import validate_json
from cryptography.hazmat.primitives import hashes
from miniopy_async import Minio, error
from miniopy_async.commonconfig import Tags


EOF = object()
storage = Blueprint('storage')


def sha256hash(bindata):
    digest = hashes.Hash(hashes.SHA256())
    digest.update(bindata)
    return b64encode(digest.finalize())


class FolderCreation(pydantic.BaseModel):
    name: str


class FolderSignature(pydantic.BaseModel):
    certificate: str
    secret: bytes


class FieldOrdering(pydantic.BaseModel):
    key: str
    order: t.Literal['asc'] | t.Literal['desc']


class FoldersListing(pydantic.BaseModel):
    offset: t.Optional[int] = 0
    limit: t.Optional[int] = 0
    sort_by: t.List[FieldOrdering] = []


class Streamer:

    def __init__(self, stream):
        self.stream = stream

    async def read(self, size: int):
        return await self.stream.read()


@storage.put("/folders/upload/<folder_id:str>", stream=True)
@openapi.definition(
    secured="token",
)
@cors(allow_headers=['Authorization', 'Content-Type', 'X-Original-Name', 'X-Folder-Definition', 'X-Checksum-SHA256'])
async def upload_to_folder(request, folder_id: str):
    userid = request.ctx.user.id
    storage = request.app.ctx.minio
    exists = await storage.bucket_exists(userid)
    if not exists:
        print(f"Bucket {userid} does not exist.")
        await storage.make_bucket(userid)


    checksum = request.headers.get('x-checksum-sha256')
    if checksum is None:
        return raw(status=422, body="SHA256 checkum is missing.")

    objname = f'{folder_id}/'
    stats = await storage.stat_object(userid, objname)

    defines = request.headers.get('x-folder-definition')
    if defines is None:
        objname = f"{folder_id}/{uuid.uuid4().hex}"
        filename = unquote(request.headers['x-original-name'])
    else:
        if defines == 'body':
            objname = f"{folder_id}/body"
            filename = "body.html"
        else:
            raise NotImplementedError('Unknown folder definition.')

    put_info = await storage.put_object(
        userid, objname,
        Streamer(request.stream), -1, part_size=5242880,
        content_type=request.headers['content-type'],
        metadata={
            "x-amz-checksum-sha256": checksum,
            "x-amz-meta-filename": filename,
        }
    )
    return json(status=200, body={
        'etag': put_info.etag,
        'userid': put_info.bucket_name,
        'fileid': put_info.object_name
    })


async def folder_fummary(
        storage, userid: str, folder_name: str, with_download: bool = False):
    objname = f'{folder_name}/'
    stats = await storage.stat_object(userid, objname)
    children = await storage.list_objects(
        userid, prefix=objname, start_after=objname
    )
    summary = {
        'userid': userid,
        'id': folder_name,
        'name': stats.metadata['x-amz-meta-title'],
        'modified': dateutil.parser.parse(
            stats.metadata['Last-Modified']
        ),
        'created': dateutil.parser.parse(
            stats.metadata['Date']
        )
    }
    contents = {}
    if children:
        for child in children:
            stats = await storage.stat_object(
                userid, child.object_name, request_headers={
                "x-amz-checksum-mode": "ENABLED"
            })
            contents[child.object_name] = {
                'checksum': stats.metadata['x-amz-checksum-sha256'],
                'name': stats.metadata['x-amz-meta-filename'],
                'content_type': stats.metadata['Content-Type'],
                'size': stats.size,
                'modified': stats.metadata['Last-Modified'],
                'created': stats.metadata['Date']
            }
            if with_download:
                contents[stats.object_name]['link'] = await storage.presigned_get_object(
                    userid, stats.object_name,
                    expires=timedelta(minutes=20)
                )
    summary['files'] = contents
    summary['locked'] = objname + 'manifest' in contents
    summary['signed'] = objname + 'signature' in contents
    return summary


@storage.get("/folders/lock/<folder_id:str>")
@openapi.definition(
    secured="token",
)
@cors(allow_headers=['Authorization', 'Content-Type'])
async def lock_folder(request, folder_id: str):
    userid = request.ctx.user.id
    storage = request.app.ctx.minio
    exists = await storage.bucket_exists(userid)
    if not exists:
        return empty(status=404)

    summary = await folder_fummary(storage, userid, folder_id)
    manifest_id = f'{folder_id}/manifest'
    if manifest_id in summary['files']:
        # Already locked.
        return empty(status=400)

    manifest = toml.dumps(summary).encode('utf-8')
    checksum = sha256hash(manifest).decode('utf-8')

    put_info = await storage.put_object(
        userid, manifest_id,
        io.BytesIO(manifest), len(manifest),
        content_type="application/toml",
        metadata={
            "x-amz-checksum-sha256": checksum,
            "x-amz-meta-filename": "manifest.toml"
        }
    )
    return empty(status=200)


@storage.post("/folders/new")
@openapi.definition(
    secured="token",
)
@validate_json(FolderCreation)
async def new_folder(request, body: FolderCreation):
    userid = request.ctx.user.id
    storage = request.app.ctx.minio

    exists = await storage.bucket_exists(userid)
    if not exists:
        print(f"Bucket {userid} does not exist.")
        await storage.make_bucket(userid)

    folderid = uuid.uuid4().hex
    result = await storage.put_object(
        userid, f'{folderid}/', io.BytesIO(b""), 0,
        content_type="application/x-folder",
        metadata={
            'title': body.name
        }
    )
    return raw(status=200, body=folderid)


@storage.post("/folders/sign/<folder_id:str>")
@openapi.definition(
    secured="token",
)
@validate_json(FolderSignature)
async def sign_folder(request, folder_id: str, body: FolderCreation):
    userid = request.ctx.user.id
    storage = request.app.ctx.minio

    exists = await storage.bucket_exists(userid)
    if not exists:
        print(f"Bucket {userid} does not exist.")
        await storage.make_bucket(userid)

    manifest_id = f'{folder_id}/manifest'
    async with aiohttp.ClientSession() as sess:
        resp = await storage.get_object(userid, manifest_id, session=sess)
        manifest = await resp.read()

    async with request.app.ctx.pki() as service:
        signature = await service.sign(
            request.ctx.user.id,
            manifest,
            body.certificate,
            body.secret
        )

    if signature['code'] == 400:
        return empty(status=400)

    if signature['code'] == 200:
        p7s = signature['body']
        checksum = sha256hash(p7s).decode('utf-8')
        put_info = await storage.put_object(
            userid, f'{folder_id}/signature',
            io.BytesIO(p7s), len(p7s),
            content_type="application/pkcs7-signature",
            metadata={
                "x-amz-checksum-sha256": checksum,
                "x-amz-meta-filename": "signature.p7s"
            }
        )
        return empty(status=200)

    raise NotImplementedError('Unknown response code.')


@storage.get("/folders/view/<folder_id:str>")
@openapi.definition(
    secured="token",
)
async def get_folder(request, folder_id: str):
    userid = request.ctx.user.id
    storage = request.app.ctx.minio

    exists = await storage.bucket_exists(userid)
    if not exists:
        return empty(status=404)

    summary = await folder_fummary(storage, userid, folder_id, with_download=True)
    body_id = f'{folder_id}/body'
    text_content = b''
    if body_id in summary['files']:
        async with aiohttp.ClientSession() as sess:
            resp = await storage.get_object(userid, body_id, session=sess)
            text_content = await resp.read()

    summary['body'] = text_content.decode('utf-8')
    return json(status=200, body=summary)


@storage.get("/folders/view/<folder_id:str>/summary")
@openapi.definition(
    secured="token",
)
async def get_folder_summary(request, folder_id: str):
    userid = request.ctx.user.id
    storage = request.app.ctx.minio

    exists = await storage.bucket_exists(userid)
    if not exists:
        return empty(status=404)

    summary = await folder_fummary(storage, userid, folder_id)
    return raw(status=200, body=toml.dumps(summary))


@storage.post("/folders")
@openapi.definition(
    secured="token",
)
@validate_json(FoldersListing)
async def list_folders(request, body: FoldersListing):
    userid = request.ctx.user.id
    storage = request.app.ctx.minio

    exists = await storage.bucket_exists(userid)
    folders = []
    if exists:
        objects = await storage.list_objects(userid)
        folders = []
        for obj in objects:
            if obj.is_dir:
                path = pathlib.PosixPath(obj.object_name)
                stats = await storage.stat_object(
                    userid, obj.object_name, request_headers={
                        "x-amz-checksum-mode": "ENABLED"
                    }
                )
                folders.append({
                    'id': path.name,
                    'name': stats.metadata['x-amz-meta-title'],
                    'modified': dateutil.parser.parse(
                        stats.metadata['Last-Modified']
                    ),
                    'created': dateutil.parser.parse(
                        stats.metadata['Date']
                    ),
                })

        if body.offset and body.limit:
            folders = folders[body.offset: body.offset+body.limit]
        elif body.offset:
            folders = folders[body.offset:]
        elif body.limit:
            folders[:body.limit]

    return json(body={
        "metadata": {
            "total": len(folders),
            "offset": body.offset,
            "page_size": body.limit or None
        },
        "items": folders
    })


@storage.listener("before_server_start")
async def setup_storage(app):
    app.ctx.minio = Minio(**app.config.MINIO)
