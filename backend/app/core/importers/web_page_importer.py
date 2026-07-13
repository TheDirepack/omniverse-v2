from app.core.document import Document, DocumentImporter
from app.db.notebook_schema import AcquisitionArtifact


class WebPageImporter(DocumentImporter):
    source_type = "web_page"

    def can_handle(self, uri: str) -> bool:
        return uri.startswith("http://") or uri.startswith("https://")

    async def fetch(
        self, uri: str, **kwargs
    ) -> Document:
        from app.core.web_fetch import web_fetcher

        result = await web_fetcher.fetch_page(uri)

        if isinstance(result, dict) and "error" not in result:
            content_text = result.get("main_content", str(result))[:100000]
            content_hash = AcquisitionArtifact.compute_hash(content_text)
            return Document(
                content_hash=content_hash,
                source_uri=uri,
                content_type=self.source_type,
                extracted_text=content_text,
                engine_name="trafilatura",
                metadata=result,
            )

        error_msg = str(result)
        return Document(
            content_hash=AcquisitionArtifact.compute_hash(error_msg),
            source_uri=uri,
            content_type=f"{self.source_type}/error",
            extracted_text="",
            metadata={"error": error_msg},
        )
