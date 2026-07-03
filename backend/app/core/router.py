import litellm
from typing import Optional, Any, List, Dict
from sqlmodel import Session, select
from app.db.session import engine
from app.db.schema import ProviderConfig, ProviderKey, AgentRouteFallback, Setting

class ModelRouter:
    def __init__(self):
        pass


    async def call_llm(self, task: str, system_prompt: str, user_prompt: str, **kwargs):
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        return await self.call_llm_with_tools(task, messages, tools=[], **kwargs)

    async def call_llm_with_tools(self, task: str, messages: List[Dict[str, str]], tools: List[Dict[str, Any]], **kwargs):
        # Remove provider_id from kwargs to avoid leaking it into litellm.acompletion
        kwargs.pop("provider_id", None)
        
        with Session(engine) as session:
            # 1. Try to get routes for this specific task sorted by priority
            routes = session.exec(select(AgentRouteFallback).where(AgentRouteFallback.task_type == task).order_by(AgentRouteFallback.priority)).all()
            
            # 2. Fallback to "DEFAULT" routes if no specific route is configured for this task
            if not routes:
                routes = session.exec(select(AgentRouteFallback).where(AgentRouteFallback.task_type == "DEFAULT").order_by(AgentRouteFallback.priority)).all()
            
            if not routes:
                raise ValueError(f"No routing configured for task '{task}' and no DEFAULT route found.")

            for route in routes:
                provider = session.get(ProviderConfig, route.provider_id) if route.provider_id else None
                if not provider or not provider.provider_type:
                    continue

                # 3. Get keys for this provider sorted by priority
                keys = session.exec(select(ProviderKey).where(ProviderKey.provider_id == provider.id).order_by(ProviderKey.priority)).all()
                
                # 4. Resolve models for this route: route-specific CSV first, then provider global CSV
                models = [m.strip() for m in (route.models or provider.models or "").split(",") if m.strip()]
                if not models:
                    continue

                for key in keys:
                    for model in models:
                        try:
                            full_model = f"{provider.provider_type}/{model}"
                            response = await litellm.acompletion(
                                model=full_model,
                                messages=messages,
                                tools=tools if tools else None,
                                tool_choice="auto" if tools else None,
                                api_key=key.api_key,
                                api_base=provider.base_url,
                                **kwargs
                            )
                            return response
                        except Exception as e:
                            print(f"[ModelRouter] Fallback failed for {full_model} with key {key.id}: {e}")
                            continue
            
            raise RuntimeError(f"All fallback options exhausted for task '{task}'.")

    def list_provider_models(self, provider_id: int) -> list[str]:
        with Session(engine) as session:
            provider = session.get(ProviderConfig, provider_id)
            if not provider or not provider.models:
                return []
            return [model.strip() for model in provider.models.split(",") if model.strip()]

router = ModelRouter()
