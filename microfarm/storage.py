import io
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

    def __init__(self, queue):
        self.queue = queue

    async def read(self, size: int):
        chunk = await self.queue.get()
        self.queue.task_done()
        if chunk is EOF:
            return
        return chunk


async def consume(queue, stream):
    hasher = hashes.Hash(hashes.SHA256())
    while True:
        chunk = await stream.read()
        if chunk is None:
            await queue.put(EOF)
            break
        hasher.update(chunk)
        await queue.put(chunk)
    return hasher.finalize().hex()


@storage.put("/folders/upload/<folder_id:str>", stream=True)
@openapi.definition(
    secured="token",
)
@cors(allow_headers=['Authorization', 'Content-Type', 'X-Original-Name', 'X-Folder-Definition'])
async def upload_to_folder(request, folder_id: str):
    userid = request.ctx.user.id
    storage = request.app.ctx.minio
    exists = await storage.bucket_exists(userid)
    if not exists:
        print(f"Bucket {userid} does not exist.")
        await storage.make_bucket(userid)

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

    queue = asyncio.Queue(3)
    streamer = Streamer(queue)
    _, hashing = await asyncio.gather(
        storage.put_object(
            userid, objname,
            streamer, -1, part_size=5242880,
            content_type=request.headers['content-type'],
            metadata={
                "x-amz-meta-filename": filename
            }
        ),
        consume(queue, request.stream)
    )

    tags = Tags(for_object=True)
    tags['hash'] = hashing
    await storage.set_object_tags(userid, objname, tags)
    return raw(status=200, body=filename)


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
        stat = await storage.stat_object(userid, child.object_name)
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
            'name': stats.metadata['x-amz-meta-filename'],
            'content_type': stats.metadata['Content-Type'],
            'modified': dateutil.parser.parse(
                stats.metadata['Last-Modified']
            ),
            'created': dateutil.parser.parse(
                stats.metadata['Date']
            )
        } for stats in contents]
    }
    return json(status=200, body=body)


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
