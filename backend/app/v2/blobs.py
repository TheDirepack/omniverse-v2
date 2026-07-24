# Integrity failures include the violated invariant for operators.
# ruff: noqa: TRY003

from __future__ import annotations

import hashlib
import os
import tempfile
from pathlib import Path


class BlobIntegrityError(IOError):
    pass


class BlobStore:
    def __init__(self, root: Path) -> None:
        self.root = Path(root)

    def path_for(self, digest: str) -> Path:
        return self.root / digest[:2] / digest[2:4] / digest

    def put(self, body: bytes) -> str:
        digest = hashlib.sha256(body).hexdigest()
        target = self.path_for(digest)
        if target.exists():
            if hashlib.sha256(target.read_bytes()).hexdigest() != digest:
                raise BlobIntegrityError("existing blob failed hash verification")
            return digest
        target.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary = tempfile.mkstemp(dir=target.parent, prefix=".blob-")
        try:
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(body)
                handle.flush()
                os.fsync(handle.fileno())
            Path(temporary).replace(target)
        finally:
            Path(temporary).unlink(missing_ok=True)
        return digest

    def get(self, digest: str) -> bytes:
        body = self.path_for(digest).read_bytes()
        if hashlib.sha256(body).hexdigest() != digest:
            raise BlobIntegrityError("blob failed hash verification")
        return body
