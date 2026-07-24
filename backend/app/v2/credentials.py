from __future__ import annotations

import json
import os
import tempfile
import threading
from pathlib import Path
from typing import Any
from uuid import uuid4

from pydantic import Field
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.v2.contracts import Contract
from app.v2.models import CredentialHealth, CredentialRef

MASK = "********"
SENSITIVE_KEYS = frozenset(
    {"authorization", "secret", "api_key", "apikey", "password", "token"}
)
_STORE_LOCK = threading.RLock()


def redact(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: MASK if key.lower() in SENSITIVE_KEYS else redact(item)
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [redact(item) for item in value]
    return value


class CredentialMetadata(Contract):
    credential_id: str
    provider_id: str
    label: str
    opaque_ref: str
    weight: int = Field(ge=1)
    mask: str = MASK


class JsonCredentialStore:
    def __init__(self, path: Path) -> None:
        self.path = Path(path)

    def _read(self) -> dict[str, str]:
        if not self.path.exists():
            return {}
        return json.loads(self.path.read_text(encoding="utf-8"))

    def put(self, secret: str) -> str:
        with _STORE_LOCK:
            opaque_ref = f"json:{uuid4().hex}"
            values = self._read()
            values[opaque_ref] = secret
            self._replace(values)
        return opaque_ref

    def delete(self, opaque_ref: str) -> None:
        with _STORE_LOCK:
            values = self._read()
            if opaque_ref not in values:
                raise KeyError(opaque_ref)
            del values[opaque_ref]
            self._replace(values)

    def resolve(self, opaque_ref: str) -> str:
        if opaque_ref.startswith("env:"):
            name = opaque_ref.removeprefix("env:")
            if name not in os.environ:
                raise KeyError(opaque_ref)
            return os.environ[name]
        try:
            return self._read()[opaque_ref]
        except KeyError:
            raise KeyError(opaque_ref) from None

    def _replace(self, values: dict[str, str]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.path.parent.chmod(0o700)
        descriptor, temporary = tempfile.mkstemp(
            dir=self.path.parent, prefix=".credentials-", text=True
        )
        try:
            os.fchmod(descriptor, 0o600)
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                json.dump(values, handle, sort_keys=True, separators=(",", ":"))
                handle.flush()
                os.fsync(handle.fileno())
            Path(temporary).replace(self.path)
            self.path.chmod(0o600)
        finally:
            Path(temporary).unlink(missing_ok=True)


class CredentialService:
    def __init__(self, store: JsonCredentialStore, engine=None) -> None:
        self.store = store
        self.engine = engine
        self._pending: dict[str, CredentialMetadata] = {}

    def add(
        self, provider_id: str, label: str, secret: str, *, weight: int = 1
    ) -> CredentialMetadata:
        credential_id = f"cred-{uuid4().hex}"
        opaque_ref = self.store.put(secret)
        metadata = CredentialMetadata(
            credential_id=credential_id,
            provider_id=provider_id,
            label=label,
            opaque_ref=opaque_ref,
            weight=weight,
        )
        if self.engine is None:
            self._pending[credential_id] = metadata
        else:
            try:
                self.persist(metadata)
            except Exception:
                self.store.delete(opaque_ref)
                raise
        return metadata

    def persist(
        self, metadata: CredentialMetadata, session: Session | None = None
    ) -> None:
        owned = session is None
        session = session or Session(self.engine)
        session.add(
            CredentialRef(
                id=metadata.credential_id,
                provider_id=metadata.provider_id,
                opaque_ref=metadata.opaque_ref,
                label=metadata.label,
                weight=metadata.weight,
                active=True,
            )
        )
        session.flush()
        session.add(CredentialHealth(credential_id=metadata.credential_id))
        if owned:
            session.commit()
            session.close()

    def ensure_persisted(self, session: Session) -> None:
        for metadata in self._pending.values():
            if session.get(CredentialRef, metadata.credential_id) is None:
                self.persist(metadata, session)
        self._pending.clear()

    def delete(self, credential_id: str) -> None:
        metadata = self._pending.pop(credential_id, None)
        if metadata is not None:
            self.store.delete(metadata.opaque_ref)
            return
        if self.engine is None:
            raise KeyError(credential_id)
        with Session(self.engine) as session, session.begin():
            row = session.get(CredentialRef, credential_id)
            if row is None:
                raise KeyError(credential_id)
            opaque_ref = row.opaque_ref
            session.execute(
                delete(CredentialHealth).where(
                    CredentialHealth.credential_id == credential_id
                )
            )
            session.delete(row)
        self.store.delete(opaque_ref)

    def resolve(self, credential: CredentialRef) -> str:
        return self.store.resolve(credential.opaque_ref)

    def list(self) -> tuple[CredentialMetadata, ...]:
        if self.engine is None:
            return tuple(self._pending.values())
        with Session(self.engine) as session:
            rows = session.scalars(
                select(CredentialRef).order_by(CredentialRef.id)
            ).all()
            return tuple(
                CredentialMetadata(
                    credential_id=row.id,
                    provider_id=row.provider_id,
                    label=row.label,
                    opaque_ref=row.opaque_ref,
                    weight=row.weight,
                )
                for row in rows
            )
