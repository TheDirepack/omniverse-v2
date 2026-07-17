from __future__ import annotations

import hashlib
import time
from typing import Any, ClassVar

from app.core.acquisition_cache import acquisition_cache
from app.core.document import Document
from app.core.gpu_detection import (
    is_gpu_available,
)
from app.db.notebook_schema import AcquisitionArtifact

_GPU_SETTING_KEY = "ocr_use_gpu"


async def _gpu_setting() -> bool | None:
    try:
        from sqlmodel import select

        from app.db.schema import Setting
        from app.db.settings_session import get_settings_session

        session = get_settings_session()
        try:
            stmt = select(Setting.value).where(Setting.key == _GPU_SETTING_KEY)
            result = session.exec(stmt).first()
            if result is not None:
                return result.lower() in ("1", "true", "yes")
            return None
        finally:
            session.close()
    except (ImportError, RuntimeError, OSError, ValueError, TypeError, KeyError):
        return None


def _resolve_gpu(preferred: bool | None, _engine: str) -> bool:
    if preferred is not None:
        return preferred
    setting = getattr(_resolve_gpu, "_cached_setting", None)
    if setting is not None:
        return setting
    return is_gpu_available()


async def _cache_gpu_setting():
    val = await _gpu_setting()
    _resolve_gpu._cached_setting = val


class OcrService:
    _docling_pipeline: ClassVar[Any | None] = None
    _easyocr_reader: ClassVar[dict[str, Any]] = {}
    _paddleocr_reader: ClassVar[dict[str, Any]] = {}

    async def ocr_image(
        self,
        image_bytes: bytes,
        source_uri: str | None = None,
        preferred_engine: str | None = None,
        use_gpu: bool | None = None,
    ) -> Document:
        content_hash = hashlib.sha256(image_bytes).hexdigest()

        cached = await acquisition_cache.get_by_hash(content_hash)
        if cached and cached.extracted_text:
            if preferred_engine and cached.engine_name != preferred_engine:
                pass
            else:
                return Document(
                    content_hash=cached.content_hash,
                    source_uri=cached.source_url or source_uri,
                    content_type=cached.content_type,
                    raw_bytes=cached.raw_bytes,
                    extracted_text=cached.extracted_text,
                    structured_data=self._parse_structured(cached.structured_data),
                    engine_name=cached.engine_name,
                    engine_version=cached.engine_version,
                    fetch_duration_ms=cached.fetch_duration_ms,
                )

        start = time.monotonic()
        doc = await self._run_ocr(image_bytes, preferred_engine, use_gpu)
        doc.content_hash = content_hash
        doc.source_uri = source_uri or doc.source_uri
        doc.fetch_duration_ms = int((time.monotonic() - start) * 1000)

        artifact = AcquisitionArtifact(
            content_hash=content_hash,
            source_url=doc.source_uri or "",
            content_type=doc.content_type,
            raw_bytes=image_bytes,
            extracted_text=doc.extracted_text,
            structured_data=str(doc.structured_data) if doc.structured_data else None,
            engine_name=doc.engine_name,
            engine_version=doc.engine_version,
            fetch_duration_ms=doc.fetch_duration_ms,
        )
        acquisition_cache.repo.store(artifact)

        return doc

    async def _run_ocr(
        self, image_bytes: bytes, preferred: str | None, use_gpu: bool | None
    ) -> Document:
        engines = self._resolve_engine_order(preferred)
        last_error: Exception | None = None
        for name, loader in engines:
            try:
                gpu = _resolve_gpu(use_gpu, name)
                engine = loader(gpu=gpu)
                return await self._ocr_with(name, engine, image_bytes)
            except (ImportError, OSError, ValueError, TypeError, RuntimeError) as e:
                last_error = e
                continue
        return Document(
            content_type="image/pending_ocr",
            extracted_text="",
            metadata={
                "error": f"OCR unavailable: {last_error}"
                if last_error else "No OCR engines installed"
            },
        )

    def _resolve_engine_order(self, preferred: str | None) -> list:
        engines = {
            "docling": ("docling", self._load_docling),
            "easyocr": ("easyocr", self._load_easyocr),
            "paddleocr": ("paddleocr", self._load_paddleocr),
            "tesseract": ("tesseract", self._load_tesseract),
        }
        if preferred and preferred in engines:
            return [engines[preferred]]
        if is_gpu_available():
            return [
                engines["easyocr"], engines["paddleocr"],
                engines["docling"], engines["tesseract"]
            ]
        return [
            engines["tesseract"], engines["easyocr"],
            engines["docling"], engines["paddleocr"]
        ]

    def _load_docling(self, _gpu: bool = False):
        if OcrService._docling_pipeline is None:
            from docling.document_converter import DocumentConverter
            OcrService._docling_pipeline = DocumentConverter()
        return OcrService._docling_pipeline

    def _load_easyocr(self, gpu: bool = False):
        gpu_key = f"easyocr_gpu_{gpu}"
        if gpu_key not in OcrService._easyocr_reader:
            import easyocr
            OcrService._easyocr_reader[gpu_key] = easyocr.Reader(
                ["en"], gpu=gpu
            )
        return OcrService._easyocr_reader[gpu_key]

    def _load_paddleocr(self, gpu: bool = False):
        gpu_key = f"paddleocr_gpu_{gpu}"
        if gpu_key not in OcrService._paddleocr_reader:
            from paddleocr import PaddleOCR
            OcrService._paddleocr_reader[gpu_key] = PaddleOCR(
                use_angle_cls=True, use_gpu=gpu, lang="en", show_log=False
            )
        return OcrService._paddleocr_reader[gpu_key]

    def _load_tesseract(self, _gpu: bool = False):
        import pytesseract
        return pytesseract

    async def _ocr_with(self, name: str, engine, image_bytes: bytes) -> Document:
        import asyncio

        structured = None

        if name == "docling":
            import tempfile
            from pathlib import Path

            def _run():
                with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp:
                    tmp.write(image_bytes)
                    tmp_path = tmp.name
                try:
                    result = engine.convert(Path(tmp_path))
                    text = result.document.export_to_text()
                    tables = [
                        table.export_to_dataframe().to_string()
                        for table in result.document.tables
                    ]
                    headings = [h.text for h in result.document.headings]
                    structured = {
                        "headings": headings,
                        "tables": tables
                    } if tables else None
                    return text, structured
                finally:
                    Path(tmp_path).unlink(missing_ok=True)

            extracted_text, structured = await asyncio.to_thread(_run)
            return Document(
                content_type="image/ocr",
                extracted_text=extracted_text,
                structured_data=structured,
                engine_name="docling",
            )

        if name == "easyocr":

            def _run():
                results = engine.readtext(image_bytes)
                lines = [r[1] for r in results]
                return "\n".join(lines)

            extracted_text = await asyncio.to_thread(_run)
            return Document(
                content_type="image/ocr",
                extracted_text=extracted_text,
                engine_name="easyocr",
                metadata={"gpu": _resolve_gpu._cached_setting or is_gpu_available()},
            )

        if name == "paddleocr":

            def _run():
                result = engine.ocr(image_bytes)
                lines = []
                if result and result[0]:
                    for line in result[0]:
                        text = (
                            line[1][0]
                            if isinstance(line, list) and len(line) > 1
                            else str(line)
                        )
                        lines.append(text)
                return "\n".join(lines)

            extracted_text = await asyncio.to_thread(_run)
            return Document(
                content_type="image/ocr",
                extracted_text=extracted_text,
                engine_name="paddleocr",
                metadata={"gpu": _resolve_gpu._cached_setting or is_gpu_available()},
            )

        if name == "tesseract":

            def _run():
                import io

                from PIL import Image
                img = Image.open(io.BytesIO(image_bytes))
                return engine.image_to_string(img)

            extracted_text = await asyncio.to_thread(_run)
            return Document(
                content_type="image/ocr",
                extracted_text=extracted_text,
                engine_name="tesseract",
            )

        return Document(
            content_type="image/pending_ocr",
            extracted_text="",
            metadata={"error": f"Unknown OCR engine: {name}"},
        )

    @staticmethod
    def _parse_structured(raw: str | None) -> dict | None:
        if not raw:
            return None
        try:
            import json
            return json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return None


ocr_service = OcrService()
