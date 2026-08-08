from dataclasses import dataclass, field
from typing import Any


SUPPORTED_FORMATS = ("markdown", "html", "full_html")
RESOURCE_MODES = ("omit", "link", "embed")

ERROR_INVALID_INPUT = "invalid_input"
ERROR_NETWORK = "network_error"
ERROR_TIMEOUT = "timeout"
ERROR_HTTP = "http_error"
ERROR_POLICY = "policy_denied"
ERROR_RESOURCE = "resource_limit"
ERROR_NO_CONTENT = "no_content"
ERROR_CONVERSION = "conversion_error"
ERROR_INTERNAL = "internal_error"

DEFAULT_TIMEOUT = 30.0


class FetchError(Exception):
    """A stable, desensitized pipeline error with a machine-readable code."""

    def __init__(self, code: str, message: str = ""):
        self.code = code
        self.message = message or code
        super().__init__(f"{self.code}: {self.message}")

    def __str__(self) -> str:
        return f"{self.code}: {self.message}"


@dataclass(frozen=True)
class FetchRequest:
    url: str
    format: str = "markdown"
    resource_mode: str = "omit"
    timeout: float = DEFAULT_TIMEOUT


@dataclass(frozen=True)
class FetchResult:
    format: str
    content: str
    metadata: dict[str, Any] = field(default_factory=dict)
