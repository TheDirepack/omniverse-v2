from sqlmodel import SQLModel, Field, Column, ForeignKey
from typing import Optional, List
from datetime import datetime

class Setting(SQLModel, table=True):
    key: str = Field(primary_key=True)
    value: Optional[str] = None

class ProviderConfig(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    provider_type: Optional[str] = None
    base_url: Optional[str] = None
    models: Optional[str] = None

class ProviderKey(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    provider_id: int = Field(sa_column=Column(ForeignKey("providerconfig.id", ondelete="CASCADE")))
    api_key: str
    priority: int = Field(default=0)

class AgentRouteFallback(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    task_type: str
    priority: int = Field(default=0)
    provider_id: Optional[int] = Field(default=None, sa_column=Column(ForeignKey("providerconfig.id", ondelete="SET NULL")))
    models: Optional[str] = None


class Universe(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True, unique=True)
    summary: Optional[str] = None
    raw_data: Optional[str] = None
    is_explored: bool = Field(default=False)

class Trait(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    universe_id: int = Field(foreign_key="universe.id")
    name: str
    value: str

class TierSystem(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    system_definition: str
    created_at: datetime = Field(default_factory=datetime.utcnow)

class WorldTier(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    universe_id: int = Field(foreign_key="universe.id")
    system_id: int = Field(foreign_key="tiersystem.id")
    tier_number: int
    justification: str

class Anomaly(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    universe_id: int = Field(foreign_key="universe.id")
    description: str
    detected_at: datetime = Field(default_factory=datetime.utcnow)

class Theory(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    universe_id: int = Field(foreign_key="universe.id")
    theory_text: str
    auditor_feedback: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

class ExecutionState(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    run_id: str
    node_name: str
    thought: str
    status: str
    state_snapshot: str
    created_at: datetime = Field(default_factory=datetime.utcnow)

class ModelConfig(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    model_name: str
    provider_id: int = Field(foreign_key="providerconfig.id")
