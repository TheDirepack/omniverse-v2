from app.db.schema import AgentRouteFallback, ProviderConfig, Universe
from sqlmodel import Session


def make_universe(session: Session, name: str = "TestUniverse") -> Universe:
    u = Universe(name=name, slug=name.lower().replace(" ", "_"))
    session.add(u)
    session.commit()
    session.refresh(u)
    return u


def make_provider(session: Session, name: str = "TestProvider") -> ProviderConfig:
    p = ProviderConfig(name=name, provider_type="openai")
    session.add(p)
    session.commit()
    session.refresh(p)
    return p


def make_route(
    session: Session, task_type: str = "RESEARCH", provider_id: int | None = None
) -> AgentRouteFallback:
    r = AgentRouteFallback(task_type=task_type, provider_id=provider_id)
    session.add(r)
    session.commit()
    session.refresh(r)
    return r
