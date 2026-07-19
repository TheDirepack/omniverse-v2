from typing import Any

from sqlmodel import Session

from app.db.settings_session import settings_engine
from app.repositories.settings import SettingsRepository


class RouteService:
    def __init__(self, session: Session | None = None):
        self.session = session

    def get_agent_routes(self) -> list[dict[str, Any]]:
        session = self.session or Session(settings_engine)
        try:
            repo = SettingsRepository(session)
            routes = repo.get_agent_routes()
            providers = repo.get_providers()
            provider_map = {p.id: p.name for p in providers if p.id}
            return [
                {
                    "id": r.id,
                    "task_type": r.task_type,
                    "provider_id": r.provider_id,
                    "models": r.models,
                    "priority": r.priority,
                    "provider_name": (
                        provider_map.get(r.provider_id) if r.provider_id else None
                    ),
                }
                for r in routes
            ]
        finally:
            if not self.session:
                session.close()

    def get_agent_route_by_id(self, route_id: int) -> dict[str, Any] | None:
        session = self.session or Session(settings_engine)
        try:
            repo = SettingsRepository(session)
            route = repo.get_route_by_id(route_id)
            if not route:
                return None
            provider = repo.get_providers()
            provider_map = {p.id: p.name for p in provider if p.id}
            return {
                "id": route.id,
                "task_type": route.task_type,
                "provider_id": route.provider_id,
                "models": route.models,
                "priority": route.priority,
                "provider_name": (
                    provider_map.get(route.provider_id) if route.provider_id else None
                ),
            }
        finally:
            if not self.session:
                session.close()

    def get_agent_route_by_task_type(self, task_type: str) -> dict[str, Any] | None:
        session = self.session or Session(settings_engine)
        try:
            repo = SettingsRepository(session)
            routes = repo.get_agent_routes_by_task_type(task_type)
            if not routes:
                return None
            route = routes[0]
            provider = repo.get_providers()
            provider_map = {p.id: p.name for p in provider if p.id}
            return {
                "id": route.id,
                "task_type": route.task_type,
                "provider_id": route.provider_id,
                "models": route.models,
                "priority": route.priority,
                "provider_name": (
                    provider_map.get(route.provider_id) if route.provider_id else None
                ),
            }
        finally:
            if not self.session:
                session.close()

    def upsert_agent_route(
        self,
        task_type: str,
        provider_id: int | None,
        models: str | None,
        priority: int = 0,
        route_id: int | None = None,
    ) -> None:
        session = self.session or Session(settings_engine)
        try:
            repo = SettingsRepository(session)
            if provider_id is not None and not repo.get_provider_by_id(provider_id):
                raise ValueError("Invalid provider_id")

            from app.db.schema import AgentRouteFallback

            route = repo.get_route_by_id(route_id) if route_id else None
            if not route:
                route = AgentRouteFallback(task_type=task_type)

            route.provider_id = provider_id
            route.models = models
            route.priority = priority
            repo.upsert_route(route)
            session.commit()
        finally:
            if not self.session:
                session.close()

    def delete_agent_route(self, route_id: int) -> bool:
        session = self.session or Session(settings_engine)
        try:
            res = SettingsRepository(session).delete_route(route_id)
            session.commit()
            return res
        finally:
            if not self.session:
                session.close()

    def reorder_routes(self, route_ids: list[int]) -> None:
        session = self.session or Session(settings_engine)
        try:
            repo = SettingsRepository(session)
            for idx, rid in enumerate(route_ids):
                route = repo.get_route_by_id(rid)
                if route:
                    route.priority = idx
                    session.add(route)
            session.commit()
        finally:
            if not self.session:
                session.close()

    def copy_default_routes_to_agent(self, agent_name: str) -> list[dict[str, Any]]:
        session = self.session or Session(settings_engine)
        try:
            repo = SettingsRepository(session)
            default_routes = repo.get_agent_routes_by_task_type("DEFAULT")
            new_routes = []
            for dr in default_routes:
                from app.db.schema import AgentRouteFallback
                route = AgentRouteFallback(
                    task_type=agent_name,
                    provider_id=dr.provider_id,
                    models=dr.models,
                    priority=dr.priority,
                )
                repo.upsert_route(route)
                session.flush()
                new_routes.append(
                    {
                        "id": route.id,
                        "task_type": route.task_type,
                        "provider_id": route.provider_id,
                        "models": route.models,
                        "priority": route.priority,
                    }
                )
            session.commit()
            return new_routes
        finally:
            if not self.session:
                session.close()
