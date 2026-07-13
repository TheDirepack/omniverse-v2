from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.ocr_service import _GPU_SETTING_KEY, OcrService, _resolve_gpu


@pytest.fixture(autouse=True)
def reset_service():
    OcrService._docling_pipeline = None
    OcrService._easyocr_reader = {}
    OcrService._paddleocr_reader = {}
    _resolve_gpu._cached_setting = None
    yield


@pytest.fixture
def svc():
    return OcrService()


SAMPLE_IMAGE = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00"
    b"\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00\x05\x18\xd8N"
    b"\x00\x00\x00\x00IEND\xaeB`\x82"
)


class TestCache:
    async def test_cache_hit_returns_doc(self, svc):
        from app.core.document import Document
        with patch.object(
            svc,
            "_run_ocr",
            new=AsyncMock(return_value=Document(
                content_hash="abc", source_uri="http://img.png",
                extracted_text="cached", engine_name="tesseract",
            )),
        ):
            doc = await svc.ocr_image(SAMPLE_IMAGE, source_uri="http://img.png")
            assert doc.engine_name == "tesseract"

    async def test_cache_hit_preferred_diff_engine_re_runs(self, svc):
        from app.core.acquisition_cache import acquisition_cache
        from app.db.notebook_schema import AcquisitionArtifact

        artifact = AcquisitionArtifact(
            content_hash="abc",
            source_url="http://img.png",
            content_type="image/ocr",
            extracted_text="old",
            engine_name="tesseract",
        )
        acquisition_cache.repo.store(artifact)

        fake_doc = MagicMock()
        fake_doc.content_hash = "abc"
        fake_doc.source_uri = "http://img.png"
        fake_doc.content_type = "image/ocr"
        fake_doc.extracted_text = "fresh"
        fake_doc.engine_name = "easyocr"
        fake_doc.engine_version = None
        fake_doc.structured_data = None
        fake_doc.metadata = {}
        fake_doc.fetch_duration_ms = 0

        with patch.object(svc, "_run_ocr", new=AsyncMock(return_value=fake_doc)):
            doc = await svc.ocr_image(
                SAMPLE_IMAGE, source_uri="http://img.png", preferred_engine="easyocr"
            )
            assert doc.extracted_text == "fresh"
            assert doc.engine_name == "easyocr"


class TestGpuResolution:
    async def _upsert_setting(self, key: str, value: str):
        from sqlalchemy import text

        from app.db.settings_session import get_settings_session
        session = get_settings_session()
        existing = session.execute(
            text("SELECT value FROM setting WHERE key = :key"), {"key": key}
        ).fetchone()
        if existing:
            session.execute(
                text("UPDATE setting SET value = :value WHERE key = :key"),
                {"value": value, "key": key}
            )
        else:
            from app.db.schema import Setting
            session.add(Setting(key=key, value=value))
        session.commit()
        session.close()

    async def _delete_setting(self, key: str):
        from sqlalchemy import text

        from app.db.settings_session import get_settings_session
        session = get_settings_session()
        session.execute(text("DELETE FROM setting WHERE key = :key"), {"key": key})
        session.commit()
        session.close()

    async def test_resolve_gpu_default_detects(self):
        with patch("app.services.ocr_service.is_gpu_available", return_value=True):
            assert _resolve_gpu(None, "easyocr") is True

    async def test_resolve_gpu_preferred_true(self):
        assert _resolve_gpu(True, "easyocr") is True

    async def test_resolve_gpu_preferred_false(self):
        assert _resolve_gpu(False, "tesseract") is False

    async def test_resolve_gpu_uses_cached_setting(self):
        _resolve_gpu._cached_setting = False
        assert _resolve_gpu(None, "easyocr") is False

    async def test_resolve_gpu_from_db_setting_true(self):
        await self._upsert_setting(_GPU_SETTING_KEY, "true")
        _resolve_gpu._cached_setting = None
        from app.services.ocr_service import _gpu_setting
        val = await _gpu_setting()
        assert val is True

    async def test_resolve_gpu_from_db_setting_false(self):
        await self._upsert_setting(_GPU_SETTING_KEY, "false")
        _resolve_gpu._cached_setting = None
        from app.services.ocr_service import _gpu_setting
        val = await _gpu_setting()
        assert val is False

    async def test_resolve_gpu_from_db_setting_none(self):
        await self._delete_setting(_GPU_SETTING_KEY)
        _resolve_gpu._cached_setting = None
        from app.services.ocr_service import _gpu_setting
        val = await _gpu_setting()
        assert val is None


class TestEngineLoaders:
    async def test_load_tesseract(self, svc):
        with patch.dict("sys.modules", {"pytesseract": MagicMock()}):
            engine = svc._load_tesseract()
            assert engine is not None

    async def test_load_easyocr_gpu_cache_key(self, svc):
        with patch("easyocr.Reader") as mock_reader:
            e1 = svc._load_easyocr(gpu=True)
            e2 = svc._load_easyocr(gpu=True)
            assert e1 is e2
            mock_reader.assert_called_once_with(["en"], gpu=True)

    async def test_load_easyocr_cpu_vs_gpu_separate(self, svc):
        mock_cpu = MagicMock()
        mock_gpu = MagicMock()
        with patch("easyocr.Reader", side_effect=[mock_cpu, mock_gpu]):
            cpu_reader = svc._load_easyocr(gpu=False)
            gpu_reader = svc._load_easyocr(gpu=True)
            assert cpu_reader is not gpu_reader

    async def test_load_docling_singleton(self, svc):
        with (
            patch.dict(
                "sys.modules",
                {"docling": MagicMock(), "docling.document_converter": MagicMock()},
            ),
            patch("app.services.ocr_service.OcrService._docling_pipeline", None),
        ):
            import importlib

            import app.services.ocr_service as ocr_mod
            importlib.reload(ocr_mod)
            OcrService._docling_pipeline = None
            d1 = svc._load_docling()
            d2 = svc._load_docling()
            assert d1 is d2

    async def test_load_paddleocr_gpu_flag(self, svc):
        fake_mod = MagicMock(spec=object())
        fake_mod.PaddleOCR = MagicMock()
        with patch.dict("sys.modules", {"paddleocr": fake_mod}):
            OcrService._paddleocr_reader = {}
            svc._load_paddleocr(gpu=True)
            fake_mod.PaddleOCR.assert_called_once_with(
                use_angle_cls=True, use_gpu=True, lang="en", show_log=False
            )


class TestEngineOrdering:
    def test_preferred_first(self, svc):
        order = svc._resolve_engine_order("tesseract")
        assert order[0][0] == "tesseract"

    def test_gpu_order_when_available(self, svc):
        with patch("app.services.ocr_service.is_gpu_available", return_value=True):
            order = svc._resolve_engine_order(None)
            names = [n for n, _ in order]
            assert names[0] == "easyocr"
            assert names[1] == "paddleocr"

    def test_cpu_order_when_no_gpu(self, svc):
        with patch("app.services.ocr_service.is_gpu_available", return_value=False):
            order = svc._resolve_engine_order(None)
            names = [n for n, _ in order]
            assert names[0] == "tesseract"


class TestRunOcr:
    async def test_all_engines_fail_import_returns_error_doc(self, svc):
        with (
            patch.object(svc, "_load_tesseract", side_effect=ImportError("tess-err")),
            patch.object(svc, "_load_easyocr", side_effect=ImportError("easy-err")),
            patch.object(svc, "_load_docling", side_effect=ImportError("docl-err")),
            patch.object(svc, "_load_paddleocr", side_effect=ImportError("padd-err")),
        ):
            doc = await svc._run_ocr(SAMPLE_IMAGE, None, None)
            assert doc.content_type == "image/pending_ocr"

    async def test_engine_failure_continues_to_next(self, svc):
        with (
            patch.object(svc, "_load_tesseract", side_effect=ImportError("no")),
        ):
            doc = await svc._run_ocr(SAMPLE_IMAGE, "tesseract", None)
            assert doc.content_type == "image/pending_ocr"

    async def test_tesseract_success(self, svc):
        fake_tesseract = MagicMock()
        fake_tesseract.image_to_string = MagicMock(return_value="hello world")
        with (
            patch.object(svc, "_load_tesseract", return_value=fake_tesseract),
            patch("PIL.Image.open", return_value=MagicMock()),
        ):
            doc = await svc._run_ocr(SAMPLE_IMAGE, "tesseract", None)
            assert doc.extracted_text == "hello world"
            assert doc.engine_name == "tesseract"
