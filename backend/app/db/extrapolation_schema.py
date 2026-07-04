from sqlmodel import SQLModel, Field
from sqlalchemy import MetaData
from typing import Optional
from datetime import datetime

extrapolation_metadata = MetaData()

class ExtrapolationModel(SQLModel):
    metadata = extrapolation_metadata

class Theory(ExtrapolationModel, table=True):
    __tablename__ = "theory"
    id: Optional[int] = Field(default=None, primary_key=True)
    universe_id: int = Field(index=True)
    theory_text: str
    auditor_feedback: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
