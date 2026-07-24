from __future__ import annotations

from dataclasses import dataclass, field
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
from app.v2.models import Run
from app.v2.projections import ResearchQueryService
from app.v2.research_runs import ResearchRunKernel
from app.v2.routing import ProviderRouter
from app.v2.search import DuckDuckGoSearch
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
    workflow: ResearchWorkflow
    worker: ResearchWorker
    http_client: httpx.AsyncClient
    adapter_status: dict[str, dict[str, object]]
    closeable_adapters: tuple[object, ...] = field(default=(), repr=False)
    _worker_task: object | None = field(default=None, repr=False)

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
        workflow=None,
    ) -> V2Runtime:
        config.validate()
        engine = cls.engine_for(config)
        client = http_client or httpx.AsyncClient(follow_redirects=False)
        blobs = BlobStore(config.blob_path)
        credentials = CredentialService(
            JsonCredentialStore(config.credentials_path), engine
        )
        router = ProviderRouter(engine, credentials, adapters or {})
        kernel = ResearchRunKernel(engine)
        adapter_status: dict[str, dict[str, object]] = {}
        resolver = resolver or ProductionResolver()
        if browser is None and config.browser_enabled and find_spec("cloakbrowser"):
            browser = BrowserAcquisition(
                resolver=resolver, concurrency=config.browser_concurrency
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
        acquisition = AcquisitionService(
            engine,
            blobs,
            resolver,
            transport or HttpxTransport(client),
            browser=browser,
            pdf=pdf,
            ocr=ocr,
        )
        research_workflow = workflow or ResearchWorkflow(
            engine,
            kernel,
            router,
            search_provider or DuckDuckGoSearch(client),
            acquisition,
            acquisition_policy=AcquisitionPolicy(
                max_body_bytes=config.max_body_bytes,
                timeout_seconds=config.http_timeout_seconds,
            ),
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
            research_workflow,
            worker,
            client,
            adapter_status,
            tuple(
                adapter
                for adapter in (browser, pdf, ocr)
                if adapter is not None and hasattr(adapter, "close")
            ),
        )

    async def startup(self, *, start_worker: bool = True) -> None:
        validate_initialized_schema(self.engine, seed_path=self.config.seed_path)
        self.research_kernel.reconcile_startup(datetime.now(timezone.utc))
        self.provider_router.refresh_adapters(
            self.http_client, timeout_seconds=self.config.http_timeout_seconds
        )
        if start_worker:
            self.worker.start()

    async def shutdown(self) -> None:
        await self.worker.stop()
        for adapter in self.closeable_adapters:
            await adapter.close()
        await self.http_client.aclose()
        self.engine.dispose()
