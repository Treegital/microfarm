import wrapt
import pydantic
import typing as t
from inspect import isawaitable
from sanic import Request
from sanic.response import json
from sanic.exceptions import SanicException


validation_error_definition = {
    "title": "ValidationError",
    "type": "object",
    "properties": {
        "loc": {
            "title": "Location", "type": "array", "items": {
                "oneOf": [
                    {"type": "string"},
                    {"type": "integer"}
                ]
            }
        },
        "msg": {"title": "Message", "type": "string"},
        "type": {"title": "Error Type", "type": "string"},
    },
    "required": ["loc", "msg", "type"],
}


validation_errors_definition = {
    "title": "ValidationErrors",
    "type": "array",
    "items": validation_error_definition
}


def validate_json(model: pydantic.BaseModel):

    @wrapt.decorator
    async def validator(wrapped, instance, args, kwargs):
        request: Request = args[0]
        if not isinstance(request, Request):
            raise SanicException("Request could not be found")

        try:
            item = model(**(request.json or {}))
        except pydantic.ValidationError as err:
            return json(err.errors(), status=422)

        retval = wrapped(*args, body=item, **kwargs)
        if isawaitable(retval):
            retval = await retval
        return retval

    return validator
