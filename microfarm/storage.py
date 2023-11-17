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


class FolderCreation(pydantic.BaseModel):
    name: str


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

    objname = f'{folder_id}/'
    stats = await storage.stat_object(userid, objname)
    children = await storage.list_objects(
        userid, prefix=objname, start_after=objname
    )

    contents = []
    text_content = b''
    text_content_id = objname + 'body'
    for child in children:
        stat = await storage.stat_object(
            userid, child.object_name, request_headers={
                "x-amz-checksum-mode": "ENABLED"
            })
        if child.object_name == text_content_id:
            async with aiohttp.ClientSession() as session:
                resp = await storage.get_object(
                    userid, child.object_name, session=session)
                text_content = await resp.read()

        contents.append(stat)

    body = {
        'id': folder_id,
        'name': stats.metadata['x-amz-meta-title'],
        'modified': dateutil.parser.parse(
            stats.metadata['Last-Modified']
        ),
        'created': dateutil.parser.parse(
            stats.metadata['Date']
        ),
        'body': text_content.decode('utf-8'),
        'contents': [{
            'id': stats.object_name,
            'checksum': stats.metadata['x-amz-checksum-sha256'],
            'name': stats.metadata['x-amz-meta-filename'],
            'content_type': stats.metadata['Content-Type'],
            'size': stats.size,
            'modified': dateutil.parser.parse(
                stats.metadata['Last-Modified']
            ),
            'created': dateutil.parser.parse(
                stats.metadata['Date']
            )
        } for stats in contents]
    }
    return json(status=200, body=body)


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

    summary = {
        'userid': userid,
        'id': folder_id
    }

    objname = f'{folder_id}/'
    children = await storage.list_objects(
        userid, prefix=objname, start_after=objname
    )
    if children:
        contents = []
        for child in children:
            stats = await storage.stat_object(userid, child.object_name)
            contents.append({
                'id': stats.object_name,
                'checksum': stats.metadata['x-amz-meta-checksum-sha256'],
                'name': stats.metadata['x-amz-meta-filename'],
                'content_type': stats.metadata['Content-Type'],
                'size': stats.size,
                'modified': stats.metadata['Last-Modified'],
                'created': stats.metadata['Date']
            })
        summary['content'] = contents

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
    if not exists:
        return json(status=200, body=[])

    objects = await storage.list_objects(userid)
    folders = []
    for obj in objects:
        if obj.is_dir:
            path = pathlib.PosixPath(obj.object_name)
            stats = await storage.stat_object(userid, obj.object_name)
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
