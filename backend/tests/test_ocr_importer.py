from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.importers.ocr_importer import OcrImporter, ocr_importer


class TestCanHandle:
    def test_image_url(self):
        assert ocr_importer.can_handle("http://example.com/img.png") is True

    def test_image_url_jpg(self):
        assert ocr_importer.can_handle("https://site.com/photo.jpg") is True

    def test_image_url_jpeg(self):
        assert ocr_importer.can_handle("https://site.com/photo.jpeg") is True

    def test_image_url_webp(self):
        assert ocr_importer.can_handle("https://site.com/img.webp") is True

    def test_image_url_tiff(self):
        assert ocr_importer.can_handle("https://site.com/img.tiff") is True

    def test_image_url_gif(self):
        assert ocr_importer.can_handle("https://site.com/img.gif") is True

    def test_image_url_bmp(self):
        assert ocr_importer.can_handle("https://site.com/img.bmp") is True

    def test_data_uri(self):
        assert ocr_importer.can_handle("data:image/png;base64,iVBORw0KGgo=") is True

    def test_non_image_url(self):
        assert ocr_importer.can_handle("https://example.com/page.html") is False

    def test_non_image_no_ext(self):
        assert ocr_importer.can_handle("https://example.com/api") is False

    def test_none(self):
        assert ocr_importer.can_handle(None) is False

    def test_empty(self):
        assert ocr_importer.can_handle("") is False


class TestFetch:
    async def test_fetch_with_image_data(self):
        import base64
        fake_doc = MagicMock()
        fake_doc.extracted_text = "hello"
        fake_doc.engine_name = "tesseract"

        with patch(
            "app.core.importers.ocr_importer.ocr_service.ocr_image",
            new=AsyncMock(return_value=fake_doc),
        ):
            doc = await ocr_importer.fetch(
                "data:image/png;base64,",
                image_data=base64.b64encode(b"fake-image").decode(),
            )
            assert doc.extracted_text == "hello"

    async def test_fetch_with_url_downloads(self):
        fake_doc = MagicMock()
        fake_doc.extracted_text = "url text"
        fake_doc.engine_name = "easyocr"

        with (
            patch("httpx.AsyncClient") as mock_client,
            patch(
                "app.core.importers.ocr_importer.ocr_service.ocr_image",
                new=AsyncMock(return_value=fake_doc),
            ),
        ):
            mock_resp = AsyncMock()
            mock_resp.content = b"downloaded-image"
            mock_resp.raise_for_status = MagicMock()
            mock_ctx = AsyncMock()
            mock_ctx.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.return_value = mock_ctx
            mock_client.get = AsyncMock(return_value=mock_resp)

            doc = await ocr_importer.fetch("http://example.com/img.png")
            assert doc.extracted_text == "url text"

    async def test_fetch_with_preferred_engine(self):
        fake_doc = MagicMock()
        fake_doc.extracted_text = "paddle result"
        fake_doc.engine_name = "paddleocr"

        with patch(
            "app.core.importers.ocr_importer.ocr_service.ocr_image",
            new=AsyncMock(return_value=fake_doc),
        ):
            doc = await ocr_importer.fetch(
                "data:image/png;base64,",
                image_data="ZmFrZQ==",
                preferred_engine="paddleocr",
            )
            assert doc.engine_name == "paddleocr"

    async def test_fetch_with_use_gpu(self):
        fake_doc = MagicMock()
        fake_doc.extracted_text = "gpu text"
        fake_doc.engine_name = "easyocr"

        with patch(
            "app.core.importers.ocr_importer.ocr_service.ocr_image",
            new=AsyncMock(return_value=fake_doc),
        ) as mock_ocr:
            await ocr_importer.fetch(
                "data:image/png;base64,",
                image_data="ZmFrZQ==",
                use_gpu=True,
            )
            mock_ocr.assert_called_once()
            _, kwargs = mock_ocr.call_args
            assert kwargs["use_gpu"] is True


class TestOcrImporterInstance:
    def test_singleton(self):
        assert isinstance(ocr_importer, OcrImporter)
