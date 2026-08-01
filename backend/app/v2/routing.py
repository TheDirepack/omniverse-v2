# ruff: noqa: SIM105

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from time import monotonic

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.v2.credentials import CredentialService
from app.v2.logging import redact
from app.v2.models import (
    CandidateHealth,
    CredentialHealth,
    CredentialRef,
    Provider,
    ProviderModel,
    Route,
    RouteCandidate,
)
from app.v2.providers import (
    AdapterKind,
    ErrorClass,
    GeminiAdapter,
    GenericOpenAIAdapter,
    ModelRequest,
    ModelResponse,
    OpenAIAdapter,
    OpenRouterAdapter,
    ProviderAdapter,
    ProviderError,
)


@dataclass(frozen=True, slots=True)
class RoutingRequirements:
    tools: bool = False
    structured: bool = False
    text: bool = True
    input_tokens: int = 0
    output_tokens: int = 0


def effective_input_window(
    provider_kind: str, context_window: int, output_tokens: int
) -> int:
    # Gemini and OpenAI both advertise combined input/output windows. Keeping this
    # branch explicit prevents compatible providers from silently changing semantics.
    if provider_kind in {"GEMINI", "OPENAI", "OPENAI_COMPATIBLE", "OPENROUTER"}:
        return max(0, context_window - output_tokens)
    return context_window


class ProviderRouter:
    def __init__(
        self,
        engine,
        credentials: CredentialService,
        adapters: dict[str, ProviderAdapter],
        *,
        clock=None,
        logger=None,
    ) -> None:
        self.engine = engine
        self.credentials = credentials
        self.adapters = adapters
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self.logger = logger

    def _log(
        self, event_type: str, message: str, *, level="INFO", data=None, **correlation
    ) -> None:
        if self.logger is None:
            return
        try:
            self.logger.log_agent(
                "provider-router",
                event_type,
                message=message,
                level=level,
                data=redact(
                    {
                        **{
                            name: correlation[name]
                            for name in ("attempt_number", "step_kind")
                            if correlation.get(name) is not None
                        },
                        **(data or {}),
                    }
                ),
                **correlation,
            )
        except Exception:
            pass

    def refresh_adapters(self, client, *, timeout_seconds: float = 60.0) -> None:
        with Session(self.engine) as session:
            providers = session.scalars(select(Provider)).all()
        factories = {
            AdapterKind.OPENAI.value: OpenAIAdapter,
            AdapterKind.GEMINI.value: GeminiAdapter,
            AdapterKind.OPENAI_COMPATIBLE.value: GenericOpenAIAdapter,
            AdapterKind.OPENROUTER.value: OpenRouterAdapter,
        }
        self.adapters = {
            provider.id: factories[provider.kind](
                client=client,
                **(
                    {"base_url": provider.base_url}
                    if provider.base_url is not None
                    else {}
                ),
                timeout_seconds=timeout_seconds,
            )
            for provider in providers
            if provider.kind in factories
        }

    def credential_health(
        self, session: Session, credential_id: str
    ) -> CredentialHealth:
        value = session.get(CredentialHealth, credential_id)
        if value is None:
            value = CredentialHealth(credential_id=credential_id)
            session.add(value)
            session.flush()
        return value

    @staticmethod
    def _active(cooldown_until: datetime | None, now: datetime) -> bool:
        if cooldown_until is None:
            return True
        if cooldown_until.tzinfo is None:
            now = now.replace(tzinfo=None)
        return cooldown_until <= now

    def _eligible_credentials(
        self, session: Session, provider_id: str, now: datetime
    ) -> list[tuple[CredentialRef, CredentialHealth]]:
        rows = session.scalars(
            select(CredentialRef).where(
                CredentialRef.provider_id == provider_id, CredentialRef.active.is_(True)
            )
        ).all()
        eligible = []
        for row in rows:
            health = self.credential_health(session, row.id)
            if not health.disabled and self._active(health.cooldown_until, now):
                eligible.append((row, health))
        return sorted(
            eligible,
            key=lambda item: (item[1].selection_count / item[0].weight, item[0].id),
        )

    async def complete(
        self,
        task: str,
        request: ModelRequest,
        requirements: RoutingRequirements,
        *,
        run_id: str | None = None,
        target_id: str | None = None,
        step_id: str | None = None,
        world_id: str | None = None,
        attempt_number: int | None = None,
        step_kind: str | None = None,
    ) -> ModelResponse:
        correlation = {
            "run_id": run_id,
            "target_id": target_id,
            "step_id": step_id,
            "world_id": world_id,
            "attempt_number": attempt_number,
            "step_kind": step_kind,
        }
        now = self.clock()
        last_retryable: ProviderError | None = None
        terminal_error: ProviderError | None = None
        with Session(self.engine) as session, session.begin():
            self.credentials.ensure_persisted(session)
        with Session(self.engine) as session:
            route = session.scalar(
                select(Route).where(Route.task == task, Route.active.is_(True))
            )
            if route is None and task != "DEFAULT":
                route = session.scalar(
                    select(Route).where(
                        Route.task == "DEFAULT", Route.active.is_(True)
                    )
                )
            candidates = (
                session.scalars(
                    select(RouteCandidate)
                    .where(RouteCandidate.route_id == route.id)
                    .order_by(RouteCandidate.position, RouteCandidate.id)
                ).all()
                if route is not None
                else []
            )
            snapshots = []
            seen_models: set[str] = set()
            for candidate in candidates:
                if candidate.model_id is not None:
                    models = [session.get(ProviderModel, candidate.model_id)]
                else:
                    models = list(
                        session.scalars(
                            select(ProviderModel)
                            .where(
                                ProviderModel.provider_id == candidate.provider_id,
                                ProviderModel.active.is_(True),
                            )
                            .order_by(ProviderModel.id)
                        )
                    )
                health = session.get(CandidateHealth, candidate.id)
                for model in models:
                    if model is None or not model.active or model.id in seen_models:
                        continue
                    provider = session.get(Provider, model.provider_id)
                    if provider is None or not provider.active:
                        continue
                    seen_models.add(model.id)
                    credentials = self._eligible_credentials(session, provider.id, now)
                    snapshots.append(
                        (
                            candidate.id,
                            model.model_name,
                            model.context_window,
                            model.output_limit,
                            model.supports_tools,
                            model.supports_structured,
                            model.supports_text,
                            provider.id,
                            provider.kind,
                            health.cooldown_until if health else None,
                            tuple((row.id, row.opaque_ref) for row, _ in credentials),
                        )
                    )
        self._log(
            "route.evaluated",
            "Provider route evaluated",
            data={
                "task": task,
                "candidate_count": len(snapshots),
                "requirements": asdict(requirements),
            },
            **correlation,
        )
        for (
            candidate_id,
            model_name,
            context_window,
            output_limit,
            supports_tools,
            supports_structured,
            supports_text,
            provider_id,
            provider_kind,
            candidate_cooldown,
            credential_refs,
        ) in snapshots:
            candidate_retryable: ProviderError | None = None
            if requirements.tools and not supports_tools:
                self._log(
                    "route.candidate.skipped",
                    "Candidate skipped",
                    data={
                        "candidate_id": candidate_id,
                        "provider_id": provider_id,
                        "model_id": model_name,
                        "reason": "TOOLS_UNSUPPORTED",
                    },
                    **correlation,
                )
                continue
            if requirements.structured and not supports_structured:
                self._log(
                    "route.candidate.skipped",
                    "Candidate skipped",
                    data={
                        "candidate_id": candidate_id,
                        "provider_id": provider_id,
                        "model_id": model_name,
                        "reason": "STRUCTURED_UNSUPPORTED",
                    },
                    **correlation,
                )
                continue
            if requirements.text and not supports_text:
                self._log(
                    "route.candidate.skipped",
                    "Candidate skipped",
                    data={
                        "candidate_id": candidate_id,
                        "provider_id": provider_id,
                        "model_id": model_name,
                        "reason": "TEXT_UNSUPPORTED",
                    },
                    **correlation,
                )
                continue
            output = (
                requirements.output_tokens
                or request.max_output_tokens
                or output_limit
                or 0
            )
            if (
                context_window is None
                or effective_input_window(provider_kind, context_window, output)
                < requirements.input_tokens
            ):
                self._log(
                    "route.candidate.skipped",
                    "Candidate skipped",
                    data={
                        "candidate_id": candidate_id,
                        "provider_id": provider_id,
                        "model_id": model_name,
                        "reason": "CONTEXT_WINDOW",
                    },
                    **correlation,
                )
                continue
            if not self._active(candidate_cooldown, now):
                self._log(
                    "route.candidate.skipped",
                    "Candidate skipped",
                    data={
                        "candidate_id": candidate_id,
                        "provider_id": provider_id,
                        "model_id": model_name,
                        "reason": "CANDIDATE_COOLDOWN",
                    },
                    **correlation,
                )
                continue
            adapter = self.adapters.get(provider_id)
            if adapter is None:
                self._log(
                    "route.candidate.skipped",
                    "Candidate skipped",
                    data={
                        "candidate_id": candidate_id,
                        "provider_id": provider_id,
                        "model_id": model_name,
                        "reason": "ADAPTER_UNAVAILABLE",
                    },
                    **correlation,
                )
                continue
            for credential_id, opaque_ref in credential_refs:
                with Session(self.engine) as session, session.begin():
                    health = self.credential_health(session, credential_id)
                    health.selection_count += 1
                routed_request = request.model_copy(update={"model": model_name})
                attempt_data = {
                    "task": task,
                    "candidate_id": candidate_id,
                    "credential_id": credential_id,
                    "provider_id": provider_id,
                    "provider_kind": provider_kind,
                    "model_id": model_name,
                }
                self._log(
                    "provider.attempt.started",
                    "Provider attempt started",
                    data=attempt_data,
                    provider_id=provider_id,
                    model_id=model_name,
                    **correlation,
                )
                started = monotonic()
                try:
                    result = await adapter.complete(
                        routed_request, self.credentials.store.resolve(opaque_ref)
                    )
                except ProviderError as error:
                    retryable = error.error_class in {
                        ErrorClass.AUTH,
                        ErrorClass.RATE_LIMIT,
                        ErrorClass.TRANSIENT,
                    }
                    failure_data = {
                        **attempt_data,
                        "duration_ms": (monotonic() - started) * 1000,
                        "error_class": error.error_class.value,
                        "error_type": type(error).__name__,
                        "error_message": str(error),
                        "status": getattr(error, "status", None),
                        "retryable": retryable,
                        "retry_after": error.retry_after,
                    }
                    self._log(
                        "provider.attempt.failed",
                        "Provider attempt failed",
                        level="WARNING" if retryable else "ERROR",
                        data=failure_data,
                        provider_id=provider_id,
                        model_id=model_name,
                        **correlation,
                    )
                    with Session(self.engine) as session, session.begin():
                        health = self.credential_health(session, credential_id)
                        if error.error_class is ErrorClass.AUTH:
                            health.last_error_class = error.error_class.value
                            health.failure_count += 1
                            health.disabled = True
                        elif error.error_class in {
                            ErrorClass.RATE_LIMIT,
                            ErrorClass.TRANSIENT,
                        }:
                            health.last_error_class = error.error_class.value
                            health.failure_count += 1
                            health.cooldown_until = now + timedelta(
                                seconds=error.retry_after or 30
                            )
                    if error.error_class is ErrorClass.AUTH:
                        self._log(
                            "provider.fallback",
                            "Falling back after provider failure",
                            level="WARNING",
                            data=failure_data,
                            **correlation,
                        )
                        continue
                    if error.error_class is ErrorClass.CAPABILITY:
                        last_retryable = error
                        self._log(
                            "provider.fallback",
                            "Falling back after provider failure",
                            level="WARNING",
                            data=failure_data,
                            **correlation,
                        )
                        break
                    if error.error_class in {
                        ErrorClass.RATE_LIMIT,
                        ErrorClass.TRANSIENT,
                    }:
                        last_retryable = error
                        candidate_retryable = error
                        self._log(
                            "provider.fallback",
                            "Falling back after provider failure",
                            level="WARNING",
                            data=failure_data,
                            **correlation,
                        )
                        continue
                    terminal_error = error
                    break
                else:
                    with Session(self.engine) as session, session.begin():
                        health = self.credential_health(session, credential_id)
                        health.failure_count = 0
                        health.last_error_class = None
                    self._log(
                        "provider.attempt.succeeded",
                        "Provider attempt succeeded",
                        data={
                            **attempt_data,
                            "duration_ms": (monotonic() - started) * 1000,
                            "usage": result.usage.model_dump(mode="json"),
                            "response_id": result.response_id,
                        },
                        provider_id=provider_id,
                        model_id=model_name,
                        **correlation,
                    )
                    return result
            if candidate_retryable is not None:
                with Session(self.engine) as session, session.begin():
                    candidate_health = session.get(CandidateHealth, candidate_id)
                    if candidate_health is None:
                        candidate_health = CandidateHealth(
                            candidate_id=candidate_id, failure_count=0
                        )
                        session.add(candidate_health)
                    candidate_health.failure_count += 1
                    candidate_health.last_error_class = (
                        candidate_retryable.error_class.value
                    )
                    candidate_health.cooldown_until = now + timedelta(
                        seconds=candidate_retryable.retry_after or 30
                    )
            if terminal_error is not None:
                break
        if terminal_error is not None:
            self._log(
                "provider.exhausted",
                "Provider routing exhausted",
                level="ERROR",
                data={"task": task, "error_class": terminal_error.error_class.value},
                **correlation,
            )
            raise terminal_error
        if last_retryable is not None:
            self._log(
                "provider.exhausted",
                "Provider routing exhausted",
                level="ERROR",
                data={"task": task, "error_class": last_retryable.error_class.value},
                **correlation,
            )
            raise last_retryable
        self._log(
            "provider.exhausted",
            "Provider routing exhausted",
            level="ERROR",
            data={"task": task, "error_class": ErrorClass.TRANSIENT.value},
            **correlation,
        )
        raise ProviderError(ErrorClass.TRANSIENT, "no healthy route")
