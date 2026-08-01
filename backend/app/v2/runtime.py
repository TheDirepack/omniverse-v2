from __future__ import annotations

import asyncio
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from importlib.util import find_spec

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.v2.acquisition import (
    AcquisitionPolicy,
    AcquisitionService,
    BrowserAcquisition,
    HttpxTransport,
    ImageOcrAdapter,
    PdfTextExtractor,
    ProductionResolver,
)
from app.v2.blobs import BlobStore
from app.v2.config import V2Config
from app.v2.credentials import CredentialService, JsonCredentialStore
from app.v2.db import create_sqlite_engine, validate_initialized_schema
from app.v2.logging import LoggingSettings, LoggingSettingsService, V2ServerLogger
from app.v2.models import CredentialRef, Provider, Run
from app.v2.preprocessing import MiniCPMPreprocessor
from app.v2.projections import ResearchQueryService
from app.v2.research_runs import ResearchRunKernel
from app.v2.routing import ProviderRouter
from app.v2.search import (
    BingBrowserSearch,
    BraveApiSearch,
    BraveBrowserSearch,
    CachedFallbackSearch,
    DuckDuckGoSearch,
    GoogleBrowserSearch,
)
from app.v2.worker import ResearchWorker
from app.v2.workflow import ResearchWorkflow


@dataclass(slots=True)
class V2Runtime:
    config: V2Config
    engine: object
    blobs: BlobStore
    credentials: CredentialService
    provider_router: ProviderRouter
    research_kernel: ResearchRunKernel
    query_service: ResearchQueryService
    acquisition: AcquisitionService
    preprocessor: object | None
    workflow: ResearchWorkflow
    worker: ResearchWorker
    http_client: httpx.AsyncClient
    adapter_status: dict[str, dict[str, object]]
    closeable_adapters: tuple[object, ...] = field(default=(), repr=False)
    _worker_task: object | None = field(default=None, repr=False)
    _remote_lifecycle_active: bool = field(default=False, repr=False)
    server_logger: V2ServerLogger = field(default_factory=V2ServerLogger, repr=False)
    logging_settings: LoggingSettingsService = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self.logging_settings = LoggingSettingsService(self.engine, self.server_logger)

    @staticmethod
    def engine_for(config: V2Config):
        return create_sqlite_engine(
            config.database_path, busy_timeout_ms=config.sqlite_busy_timeout_ms
        )

    @classmethod
    def build(
        cls,
        config: V2Config,
        *,
        http_client: httpx.AsyncClient | None = None,
        adapters: dict | None = None,
        search_provider=None,
        resolver=None,
        transport=None,
        browser=None,
        pdf=None,
        ocr=None,
        preprocessor=None,
        workflow=None,
        server_logger: V2ServerLogger | None = None,
    ) -> V2Runtime:
        config.validate()
        engine = cls.engine_for(config)
        activity_logger = server_logger or V2ServerLogger(config.logging_root)
        client = http_client or httpx.AsyncClient(follow_redirects=False)
        blobs = BlobStore(config.blob_path)
        credentials = CredentialService(
            JsonCredentialStore(config.credentials_path), engine
        )
        router = ProviderRouter(
            engine, credentials, adapters or {}, logger=activity_logger
        )
        kernel = ResearchRunKernel(engine)
        adapter_status: dict[str, dict[str, object]] = {}
        resolver = resolver or ProductionResolver()
        if browser is None and config.browser_enabled and find_spec("cloakbrowser"):
            browser = BrowserAcquisition(
                resolver=resolver,
                concurrency=config.browser_concurrency,
                profile_path=config.browser_profile_path,
            )
        if browser is None:
            adapter_status["browser"] = {
                "available": False,
                "detail": (
                    "disabled by configuration"
                    if not config.browser_enabled
                    else "cloakbrowser package unavailable"
                ),
            }
        else:
            adapter_status["browser"] = (
                browser.status()
                if hasattr(browser, "status")
                else {"available": True, "detail": "injected adapter"}
            )
        pdf = pdf or PdfTextExtractor(
            max_pages=config.pdf_max_pages,
            max_characters=config.pdf_max_characters,
        )
        ocr = ocr or ImageOcrAdapter(
            max_bytes=config.ocr_max_bytes,
            max_pixels=config.ocr_max_pixels,
            timeout_seconds=config.ocr_timeout_seconds,
        )
        adapter_status["pdf"] = pdf.status()
        adapter_status["ocr"] = ocr.status()
        if preprocessor is None and config.preprocessor_enabled:
            preprocessor = MiniCPMPreprocessor(
                base_url=config.preprocessor_base_url,
                model=config.preprocessor_model,
                timeout_seconds=config.preprocessor_timeout_seconds,
                concurrency=config.preprocessor_concurrency,
                client=client,
                logger=activity_logger,
            )
        adapter_status["preprocessor"] = (
            preprocessor.status()
            if preprocessor is not None
            else {"available": False, "detail": "disabled by configuration"}
        )
        acquisition = AcquisitionService(
            engine,
            blobs,
            resolver,
            transport or HttpxTransport(client),
            browser=browser,
            pdf=pdf,
            ocr=ocr,
            preprocessor=preprocessor,
            logger=activity_logger,
        )
        if search_provider is None:
            search_providers = (DuckDuckGoSearch(client, logger=activity_logger),)
            if browser is not None:
                search_policy = AcquisitionPolicy(
                    max_body_bytes=config.max_body_bytes,
                    timeout_seconds=config.browser_search_timeout_seconds,
                )
                search_providers += (
                    GoogleBrowserSearch(browser, search_policy, logger=activity_logger),
                    BingBrowserSearch(browser, search_policy, logger=activity_logger),
                    BraveBrowserSearch(browser, search_policy, logger=activity_logger),
                )
            def brave_api_key() -> str | None:
                with Session(engine) as session:
                    credential = session.scalar(
                        select(CredentialRef)
                        .join(Provider)
                        .where(
                            Provider.id == "brave-search",
                            Provider.kind == "BRAVE_SEARCH",
                            Provider.active.is_(True),
                            CredentialRef.active.is_(True),
                        )
                        .order_by(CredentialRef.id)
                    )
                try:
                    return credentials.resolve(credential) if credential else None
                except KeyError:
                    return None

            final_search_providers = (
                BraveApiSearch(
                    client, credential_getter=brave_api_key, logger=activity_logger
                ),
            )
        elif isinstance(search_provider, (tuple, list)):
            search_providers = tuple(search_provider)
            final_search_providers = ()
        else:
            search_providers = (search_provider,)
            final_search_providers = ()
        research_workflow = workflow or ResearchWorkflow(
            engine,
            kernel,
            router,
            CachedFallbackSearch(
                search_providers,
                final_providers=final_search_providers,
                logger=activity_logger,
            ),
            acquisition,
            preprocessor=preprocessor,
            acquisition_policy=AcquisitionPolicy(
                max_body_bytes=config.max_body_bytes,
                timeout_seconds=config.http_timeout_seconds,
            ),
            logger=activity_logger,
        )
        run_cursor = {"last": None}

        def next_run() -> str | None:
            with Session(engine) as session:
                ids = list(
                    session.scalars(
                        select(Run.id)
                        .where(
                            Run.status.in_(
                                ("PENDING", "RUNNING", "WAITING_RETRY", "CANCELLING")
                            )
                        )
                        .order_by(Run.created_at, Run.id)
                    )
                )
            if not ids:
                return None
            prior = run_cursor["last"]
            index = (ids.index(prior) + 1) % len(ids) if prior in ids else 0
            run_cursor["last"] = ids[index]
            return ids[index]

        worker = ResearchWorker(
            kernel,
            research_workflow,
            next_run=next_run,
            poll_seconds=config.worker_poll_seconds,
            reclaim_seconds=config.worker_reclaim_seconds,
            concurrency=config.worker_concurrency,
            logger=activity_logger,
        )
        return cls(
            config,
            engine,
            blobs,
            credentials,
            router,
            kernel,
            ResearchQueryService(engine),
            acquisition,
            preprocessor,
            research_workflow,
            worker,
            client,
            adapter_status,
            tuple(
                adapter
                for adapter in (browser, pdf, ocr, preprocessor)
                if adapter is not None and hasattr(adapter, "close")
            ),
            server_logger=activity_logger,
        )

    async def startup(self, *, start_worker: bool = True) -> None:
        validate_initialized_schema(self.engine, seed_path=self.config.seed_path)
        self.logging_settings.load_and_apply()
        self.server_logger.log_event(
            "server", "INFO", "server.started", "runtime", "V2 runtime started"
        )
        self.research_kernel.reconcile_startup(datetime.now(timezone.utc))
        if self.config.remote_model_lifecycle_enabled:
            self._remote_lifecycle_active = True
            await self._manage_remote_models("start")
        self.provider_router.refresh_adapters(
            self.http_client, timeout_seconds=self.config.http_timeout_seconds
        )
        self.refresh_adapter_status()
        if start_worker:
            self.worker.start()

    async def _manage_remote_models(self, action: str) -> None:
        from app.v2.preprocessor_ssh import PreprocessorSSH

        configurations = []
        if self.config.preprocessor_enabled:
            configurations.append(("MiniCPM", self.config))
        configurations.append(
            (
                "Qwen",
                replace(
                    self.config,
                    preprocessor_base_url=self.config.qwen_base_url,
                    preprocessor_model=self.config.qwen_model,
                    preprocessor_remote_script=self.config.qwen_remote_script,
                ),
            )
        )
        for name, config in configurations:
            await self._manage_remote_model(name, config, action, PreprocessorSSH)

    async def _manage_remote_model(
        self, name: str, config: V2Config, action: str, manager_type
    ) -> None:
        try:
            manager = manager_type(
                config, self.credentials, logger=self.server_logger, remote_model=name
            )
            operation = (
                manager.start_server if action == "start" else manager.stop_server
            )
            changed, message = await asyncio.to_thread(operation)
            self.server_logger.log_event(
                "server",
                "INFO",
                f"remote_model.{action}",
                "runtime",
                f"{name}: {message}",
                data={"model": name, "changed": changed},
            )
        except Exception as error:
            self.server_logger.log_event(
                "server",
                "ERROR",
                f"remote_model.{action}.failed",
                "runtime",
                f"{name} remote lifecycle operation failed",
                data={"model": name, "error_class": type(error).__name__},
            )

    def refresh_adapter_status(self) -> None:
        status = (
            self.preprocessor.status()
            if self.preprocessor is not None
            else {"available": False, "detail": "disabled by configuration"}
        )
        if self.preprocessor is not None and self.config.preprocessor_enabled:
            try:
                from app.v2.preprocessor_ssh import PreprocessorSSH

                ssh = PreprocessorSSH(self.config, self.credentials)
                if ssh.check_running():
                    status["detail"] += " — server running"
                else:
                    status["detail"] += " — server not running (click Start)"
            except Exception:
                status["detail"] += " — unreachable"
        elif not self.config.preprocessor_enabled:
            status["detail"] = "disabled by configuration"
        self.adapter_status["preprocessor"] = status

    def reconfigure_preprocessor(self, **changes: object) -> None:
        config = replace(self.config, **changes)
        config.validate()
        preprocessor = (
            MiniCPMPreprocessor(
                base_url=config.preprocessor_base_url,
                model=config.preprocessor_model,
                timeout_seconds=config.preprocessor_timeout_seconds,
                concurrency=config.preprocessor_concurrency,
                client=self.http_client,
                logger=self.server_logger,
            )
            if config.preprocessor_enabled
            else None
        )
        self.config = config
        self.preprocessor = preprocessor
        self.acquisition.preprocessor = preprocessor
        self.workflow.preprocessor = preprocessor
        self.refresh_adapter_status()

    async def shutdown(self) -> None:
        self.server_logger.log_event(
            "server", "INFO", "server.stopping", "runtime", "V2 runtime stopping"
        )
        try:
            await self.worker.stop()
            if self._remote_lifecycle_active:
                await self._manage_remote_models("stop")
                self._remote_lifecycle_active = False
            for adapter in self.closeable_adapters:
                await adapter.close()
            await self.http_client.aclose()
        finally:
            self.server_logger.log_event(
                "server", "INFO", "server.stopped", "runtime", "V2 runtime stopped"
            )
            self.server_logger.close()
            self.engine.dispose()

    def update_logging_settings(
        self, value: LoggingSettings | dict[str, object]
    ) -> LoggingSettings:
        settings = (
            value
            if isinstance(value, LoggingSettings)
            else LoggingSettings.from_dict(
                {**self.logging_settings.settings.to_dict(), **value}
            )
        )
        return self.logging_settings.update(settings)
