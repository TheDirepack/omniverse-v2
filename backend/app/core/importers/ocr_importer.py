import base64

import httpx

from app.core.document import Document, DocumentImporter
from app.services.ocr_service import ocr_service


class OcrImporter(DocumentImporter):
    def can_handle(self, uri: str) -> bool:
        if not uri:
            return False
        uri_lower = uri.lower()
        image_exts = (".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp", ".tiff", ".tif")
        if uri_lower.startswith("data:image/"):
            return True
        return bool(any(uri_lower.endswith(ext) for ext in image_exts))

    async def fetch(
        self, uri: str, **kwargs
    ) -> Document:
        preferred = kwargs.get("preferred_engine")
        image_data = kwargs.get("image_data")
        use_gpu = kwargs.get("use_gpu")

        if image_data:
            image_bytes = base64.b64decode(image_data)
        elif uri.startswith("data:"):
            _, encoded = uri.split(",", 1)
            image_bytes = base64.b64decode(encoded)
        else:
            async with httpx.AsyncClient(timeout=60, follow_redirects=True) as client:
                resp = await client.get(uri)
                resp.raise_for_status()
                image_bytes = resp.content

        return await ocr_service.ocr_image(
            image_bytes=image_bytes,
            source_uri=uri,
            preferred_engine=preferred,
            use_gpu=use_gpu,
        )


ocr_importer = OcrImporter()
