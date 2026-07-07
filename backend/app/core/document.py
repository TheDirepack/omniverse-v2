from dataclasses import dataclass, field
from typing import Any, Optional

@dataclass
class Document:
    content_type: str = "text/plain"
    extracted_text: str = ""
    content_hash: Optional[str] = None
    source_uri: Optional[str] = None
    raw_bytes: Optional[bytes] = None
    structured_data: Optional[Any] = None
    engine_name: Optional[str] = None
    engine_version: Optional[str] = None
    fetch_duration_ms: int = 0
    metadata: dict = field(default_factory=dict)

class DocumentImporter:
    def can_handle(self, uri: str) -> bool:
        raise NotImplementedError

    async def fetch(self, uri: str, **kwargs) -> Document:
        raise NotImplementedError
