from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.v2.models import ProviderModel

_MODEL_NAME_UNIQUE_ERROR = (
    "UNIQUE constraint failed: provider_model.provider_id, provider_model.model_name"
)


class ProviderModelNameConflictError(ValueError):
    pass


class ProviderModelOwnershipConflictError(ValueError):
    pass


def upsert_provider_model(
    session: Session,
    *,
    provider_id: str,
    model_id: str,
    values: dict[str, Any],
) -> ProviderModel:
    model_name = str(values["model_name"])
    duplicate_id = session.scalar(
        select(ProviderModel.id).where(
            ProviderModel.provider_id == provider_id,
            ProviderModel.model_name == model_name,
            ProviderModel.id != model_id,
        )
    )
    if duplicate_id is not None:
        raise ProviderModelNameConflictError

    row = session.get(ProviderModel, model_id)
    if row is None:
        row = ProviderModel(id=model_id, provider_id=provider_id, **values)
        session.add(row)
    elif row.provider_id != provider_id:
        raise ProviderModelOwnershipConflictError
    else:
        for key, value in values.items():
            setattr(row, key, value)
    try:
        session.flush()
    except IntegrityError as error:
        if _MODEL_NAME_UNIQUE_ERROR in str(error.orig):
            raise ProviderModelNameConflictError from error
        raise
    return row
