from datetime import datetime

from sqlalchemy import MetaData
from sqlmodel import Field, SQLModel

extrapolation_metadata = MetaData()


class ExtrapolationModel(SQLModel):
    metadata = extrapolation_metadata


class Theory(ExtrapolationModel, table=True):
    __tablename__ = "theory"
    id: int | None = Field(default=None, primary_key=True)
    universe_id: int = Field(index=True)
    theory_text: str
    auditor_feedback: str | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
