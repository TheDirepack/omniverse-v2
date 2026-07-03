import litellm
from typing import Optional, Any, List, Dict
from sqlmodel import Session, select
from app.db.session import engine
from app.db.schema import ProviderConfig, ProviderKey, AgentRouteFallback, Setting

class ModelRouter:
    def __init__(self):
        pass

    def get_general_setting(self, key: str) -> Optional[str]:
        with Session(engine) as session:
            statement = select(Setting).where(Setting.key == key)
            setting = session.exec(statement).first()
            return setting.value if setting else None

    async def call_llm(self, task: str, system_prompt: str, user_prompt: str, **kwargs):
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        return await self.call_llm_with_tools(task, messages, tools=[], **kwargs)

    async def call_llm_with_tools(self, task: str, messages: List[Dict[str, str]], tools: List[Dict[str, Any]], **kwargs):
        with Session(engine) as session:
            # 1. Get routes for this task sorted by priority
            routes = session.exec(select(AgentRouteFallback).where(AgentRouteFallback.task_type == task).order_by(AgentRouteFallback.priority)).all()
            
            if not routes:
                raise ValueError(f"Task '{task}' routing is not configured. No fallback routes found.")

            for route in routes:
                provider = session.get(ProviderConfig, route.provider_id) if route.provider_id else None
                if not provider or not provider.provider_type:
                    continue

                # 2. Get keys for this provider sorted by priority
                keys = session.exec(select(ProviderKey).where(ProviderKey.provider_id == provider.id).order_by(ProviderKey.priority)).all()
                
                # 3. Get models for this provider
                provider_models = [m.strip() for m in (provider.models or "").split(",") if m.strip()]
                if route.model_name and route.model_name not in provider_models:
                    provider_models.insert(0, route.model_name)
                elif not provider_models:
                    # No models defined in provider, but we have route.model_name
                    if route.model_name:
                        provider_models = [route.model_name]
                    else:
                        continue

                for key in keys:
                    for model in provider_models:
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
                            print(f"[ModelRouter] Fallback failed for {full_model} with key {key.id[:5] if hasattr(key.id, 'startswith') else '?'}: {e}")
                            continue
            
            raise RuntimeError(f"All fallback options exhausted for task '{task}'.")

    def list_provider_models(self, provider_id: int) -> list[str]:
        with Session(engine) as session:
            provider = session.get(ProviderConfig, provider_id)
            if not provider or not provider.models:
                return []
            return [model.strip() for model in provider.models.split(",") if model.strip()]

router = ModelRouter()


router = ModelRouter()
