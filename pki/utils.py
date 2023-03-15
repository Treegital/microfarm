import typing as t
from pathlib import Path


def data_from_file(path: t.Union[Path, str]) -> t.Optional[bytes]:
    path = Path(path)  # idempotent.
    if not path.exists():
        return None

    if not path.is_file():
        raise TypeError('{path!r} should be a file.')

    with path.open('rb') as fd:
        data = fd.read()

    return data


def data_to_file(path: t.Union[Path, str], data: bytes):
    path = Path(path)  # idempotent.
    if path.exists() and not path.is_file():
        raise TypeError('{path!r} should be a file.')

    with path.open('wb') as fd:
        fd.write(data)
