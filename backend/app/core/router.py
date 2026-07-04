import litellm
import re
from typing import Optional, Any, List, Dict
from sqlmodel import Session, select
from app.db.session import engine
from app.db.schema import ProviderConfig, ProviderKey, AgentRouteFallback, Setting, ExecutionState

def _clean_error(e: Exception) -> str:
    msg = str(e).split('\n')[0]
    if " - {" in msg:
        msg = msg.split(" - {")[0]
    msg = re.sub(r'^(litellm\.\w+Error: )+', r'\1', msg)
    return msg.strip()

class ModelRouter:
    def __init__(self):
        pass

    async def run_model(self, task: str, messages: List[Dict[str, str]], tools: Optional[List[Dict[str, Any]]] = None, run_id: Optional[str] = None, **kwargs):
        """
        High-level entry point for model calls.
        """
        return await self.call_llm_with_tools(task, messages, tools or [], run_id=run_id, **kwargs)

    async def call_llm(self, task: str, system_prompt: str, user_prompt: str, run_id: Optional[str] = None, **kwargs):
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        return await self.run_model(task, messages, tools=[], run_id=run_id, **kwargs)

    async def call_llm_with_tools(self, task: str, messages: List[Dict[str, str]], tools: List[Dict[str, Any]], run_id: Optional[str] = None, **kwargs):
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
            
            # Collect all candidate configurations first
            candidates = []
            for route in routes:
                provider = session.get(ProviderConfig, route.provider_id) if route.provider_id else None
                if not provider or not provider.provider_type:
                    continue
                
                keys = session.exec(select(ProviderKey).where(ProviderKey.provider_id == provider.id).order_by(ProviderKey.priority)).all()
                if not keys and provider.provider_type in {"ollama", "custom"}:
                    keys = [ProviderKey(id=-1, api_key="", priority=0)]

                models = [m.strip() for m in (route.models or provider.models or "").split(",") if m.strip()]
                
                for key in keys:
                    for model in models:
                        model_prefix = "openai" if provider.provider_type == "custom" else provider.provider_type
                        candidates.append({
                            "provider": provider,
                            "key": key,
                            "model": model,
                            "full_model": f"{model_prefix}/{model}"
                        })

            for candidate in candidates:
                try:
                    full_model = candidate["full_model"]
                    response = await litellm.acompletion(
                        model=full_model,
                        messages=messages,
                        tools=tools if tools else None,
                        tool_choice="auto" if tools else None,
                        api_key=candidate["key"].api_key,
                        api_base=candidate["provider"].base_url,
                        **kwargs
                    )
                    return response
                except Exception as e:
                    if run_id:
                        with Session(engine) as log_session:
                            clean_e = _clean_error(e)
                            log_entry = ExecutionState(
                                run_id=run_id,
                                node_name="ModelRouter",
                                thought=f"Fallback: {candidate['full_model']} failed due to {clean_e}. Trying next candidate.",
                                status="INFO",
                                state_snapshot="{}"
                            )
                            log_session.add(log_entry)
                            log_session.commit()
                    print(f"[ModelRouter] Fallback failed for {candidate['full_model']} with key {candidate['key'].id}: {_clean_error(e)}")
                    continue
            
            raise RuntimeError(f"All fallback options exhausted for task '{task}'.")


    def list_provider_models(self, provider_id: int) -> list[str]:
        with Session(engine) as session:
            provider = session.get(ProviderConfig, provider_id)
            if not provider or not provider.models:
                return []
            return [model.strip() for model in provider.models.split(",") if model.strip()]

router = ModelRouter()
