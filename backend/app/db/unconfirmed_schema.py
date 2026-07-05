from sqlmodel import SQLModel, Field
from sqlalchemy import MetaData
from typing import Optional
from datetime import datetime

unconfirmed_metadata = MetaData()


class UnconfirmedModel(SQLModel):
    metadata = unconfirmed_metadata


class UnconfirmedUniverse(UnconfirmedModel, table=True):
    __tablename__ = "unconfirmed_universe"

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True, unique=True)
    source_wikis: Optional[str] = None
    raw_data: Optional[str] = None
    summary: Optional[str] = None
    research_status: Optional[str] = None
    is_explored: bool = Field(default=False)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class UnconfirmedTrait(UnconfirmedModel, table=True):
    __tablename__ = "unconfirmed_trait"

    id: Optional[int] = Field(default=None, primary_key=True)
    universe_id: int = Field(foreign_key="unconfirmed_universe.id")
    category: Optional[str] = None
    name: str
    value: str
    canon_status: Optional[str] = None
    reference: Optional[str] = None
    wiki_source: Optional[str] = None
    confidence: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class UnconfirmedClaim(UnconfirmedModel, table=True):
    __tablename__ = "unconfirmed_claim"

    id: Optional[int] = Field(default=None, primary_key=True)
    universe_id: int = Field(foreign_key="unconfirmed_universe.id")
    subject: str
    predicate: str
    object_val: str
    reference: Optional[str] = None
    wiki_source: Optional[str] = None
    confidence: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
