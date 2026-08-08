from dataclasses import dataclass, field
from typing import Any


SUPPORTED_FORMATS = ("markdown", "html", "full_html")
RESOURCE_MODES = ("omit", "link", "embed")


@dataclass(frozen=True)
class FetchRequest:
    url: str
    format: str = "markdown"
    resource_mode: str = "omit"


@dataclass(frozen=True)
class FetchResult:
    format: str
    content: str
    metadata: dict[str, Any] = field(default_factory=dict)
