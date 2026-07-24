from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.v2.credentials import CredentialService
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
    if provider_kind in {"GEMINI", "OPENAI", "OPENAI_COMPATIBLE"}:
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
    ) -> None:
        self.engine = engine
        self.credentials = credentials
        self.adapters = adapters
        self.clock = clock or (lambda: datetime.now(timezone.utc))

    def refresh_adapters(self, client, *, timeout_seconds: float = 60.0) -> None:
        with Session(self.engine) as session:
            providers = session.scalars(select(Provider)).all()
        factories = {
            AdapterKind.OPENAI.value: OpenAIAdapter,
            AdapterKind.GEMINI.value: GeminiAdapter,
            AdapterKind.OPENAI_COMPATIBLE.value: GenericOpenAIAdapter,
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
        self, task: str, request: ModelRequest, requirements: RoutingRequirements
    ) -> ModelResponse:
        now = self.clock()
        last_retryable: ProviderError | None = None
        terminal_error: ProviderError | None = None
        with Session(self.engine) as session, session.begin():
            self.credentials.ensure_persisted(session)
        with Session(self.engine) as session:
            rows = session.execute(
                select(RouteCandidate, ProviderModel, Provider)
                .join(Route, Route.id == RouteCandidate.route_id)
                .join(ProviderModel, ProviderModel.id == RouteCandidate.model_id)
                .join(Provider, Provider.id == ProviderModel.provider_id)
                .where(
                    Route.task == task,
                    Route.active.is_(True),
                    Provider.active.is_(True),
                    ProviderModel.active.is_(True),
                )
                .order_by(Route.position, RouteCandidate.position, RouteCandidate.id)
            ).all()
            snapshots = []
            for candidate, model, provider in rows:
                health = session.get(CandidateHealth, candidate.id)
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
                continue
            if requirements.structured and not supports_structured:
                continue
            if requirements.text and not supports_text:
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
                continue
            if not self._active(candidate_cooldown, now):
                continue
            adapter = self.adapters.get(provider_id)
            if adapter is None:
                continue
            for credential_id, opaque_ref in credential_refs:
                with Session(self.engine) as session, session.begin():
                    health = self.credential_health(session, credential_id)
                    health.selection_count += 1
                routed_request = request.model_copy(update={"model": model_name})
                try:
                    result = await adapter.complete(
                        routed_request, self.credentials.store.resolve(opaque_ref)
                    )
                except ProviderError as error:
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
                        continue
                    if error.error_class in {
                        ErrorClass.RATE_LIMIT,
                        ErrorClass.TRANSIENT,
                    }:
                        last_retryable = error
                        candidate_retryable = error
                        continue
                    terminal_error = error
                    break
                else:
                    with Session(self.engine) as session, session.begin():
                        health = self.credential_health(session, credential_id)
                        health.failure_count = 0
                        health.last_error_class = None
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
            raise terminal_error
        if last_retryable is not None:
            raise last_retryable
        raise ProviderError(ErrorClass.TRANSIENT, "no healthy route")
