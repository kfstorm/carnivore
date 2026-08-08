import asyncio
import tempfile
from urllib.parse import urlsplit

from .lib import Carnivore
from .models import (
    ERROR_CONVERSION,
    ERROR_INVALID_INPUT,
    ERROR_NO_CONTENT,
    ERROR_RESOURCE,
    ERROR_TIMEOUT,
    FetchError,
    FetchRequest,
    FetchResult,
    RESOURCE_MODES,
    SUPPORTED_FORMATS,
)
from .render import MAX_OUTPUT_BYTES, render_browser


def validate_request(request: FetchRequest) -> None:
    parsed = urlsplit(request.url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise FetchError(ERROR_INVALID_INPUT, "URL must be an absolute HTTP(S) URL")
    if request.format not in SUPPORTED_FORMATS:
        raise FetchError(ERROR_INVALID_INPUT, "Unsupported format")
    if request.resource_mode not in RESOURCE_MODES:
        raise FetchError(ERROR_INVALID_INPUT, "Unsupported resource mode")
    if request.timeout <= 0:
        raise FetchError(ERROR_INVALID_INPUT, "Timeout must be a positive number")


class FetchPipeline:
    """Coordinate fetch stages behind the public fetch(request) seam."""

    async def fetch(self, request: FetchRequest) -> FetchResult:
        try:
            async with asyncio.timeout(request.timeout):
                return await self._fetch_within_budget(request)
        except asyncio.TimeoutError:
            raise FetchError(
                ERROR_TIMEOUT, f"Timed out after {request.timeout} seconds"
            )

    async def _fetch_within_budget(self, request: FetchRequest) -> FetchResult:
        validate_request(request)
        rendered_html = await render_browser(request.url, request.timeout)
        client = Carnivore(
            [request.format],
            tempfile.gettempdir(),
            resource_mode=request.resource_mode,
        )
        try:
            extracted = await client._get_polished_data(rendered_html)
        except FetchError:
            raise
        except Exception:
            raise FetchError(ERROR_NO_CONTENT, "Fetched content is empty")
        if not extracted or not extracted.get("html"):
            raise FetchError(ERROR_NO_CONTENT, "Fetched content is empty")
        try:
            content = await self._convert(client, request, rendered_html, extracted)
        except FetchError:
            raise
        except Exception:
            raise FetchError(ERROR_CONVERSION, "Content conversion failed")
        if not content:
            raise FetchError(ERROR_NO_CONTENT, "Fetched content is empty")
        if len(content.encode("utf-8")) > MAX_OUTPUT_BYTES:
            raise FetchError(ERROR_RESOURCE, "Output too large")
        metadata = {
            key: value
            for key, value in extracted.get("metadata", {}).items()
            if key.lower() != "url" and value not in (None, "")
        }
        return FetchResult(format=request.format, content=content, metadata=metadata)

    async def _convert(self, client, request, rendered_html, extracted):
        polished_html = extracted["html"]
        if request.format == "full_html":
            html = rendered_html
            if request.resource_mode == "omit":
                return client._remove_resources(html)
            if request.resource_mode == "embed":
                return await client._get_embedded_html(
                    request.url, html, "rendered HTML"
                )
            return html

        html = polished_html
        if request.resource_mode == "omit":
            html = client._remove_resources(html)
        elif request.resource_mode == "embed":
            html = await client._get_embedded_html(request.url, html, "polished HTML")
        if request.format == "html":
            return html
        try:
            markdown = await client._get_markdown(html, "polished HTML")
        except Exception:
            markdown = None
        if markdown:
            return markdown
        rendered_html = client._remove_resources(rendered_html)
        return await client._get_markdown(rendered_html, "rendered HTML")


async def fetch(request: FetchRequest) -> FetchResult:
    return await FetchPipeline().fetch(request)
