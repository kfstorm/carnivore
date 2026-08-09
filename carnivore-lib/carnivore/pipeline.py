import asyncio
import hashlib
import json
from urllib.parse import urlsplit

from .cache import read_fetch_result, write_fetch_result
from .convert import embed_html, html_to_markdown, remove_resources
from .extract import extract_readability
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


PIPELINE_ID = "fetch-pipeline"
LOADING_STRATEGY_ID = "browser-domcontentloaded-settle-v1"


def _cache_key(request: FetchRequest) -> str:
    key_data = {
        "pipeline_id": PIPELINE_ID,
        "url_sha256": hashlib.sha256(request.url.encode("utf-8")).hexdigest(),
        "format": request.format,
        "resource_mode": request.resource_mode,
        "loading_strategy_id": LOADING_STRATEGY_ID,
    }
    return hashlib.sha256(
        json.dumps(key_data, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


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
        validate_request(request)
        cache_key = _cache_key(request)
        cached_result = read_fetch_result(cache_key, FetchResult)
        if cached_result is not None:
            return cached_result
        try:
            async with asyncio.timeout(request.timeout):
                result = await self._fetch_within_budget(request)
        except asyncio.TimeoutError:
            raise FetchError(
                ERROR_TIMEOUT, f"Timed out after {request.timeout} seconds"
            )
        write_fetch_result(cache_key, result)
        return result

    async def _fetch_within_budget(self, request: FetchRequest) -> FetchResult:
        rendered_html = await render_browser(request.url, request.timeout)
        try:
            extracted = await extract_readability(rendered_html)
        except FetchError:
            raise
        except Exception:
            raise FetchError(ERROR_NO_CONTENT, "Fetched content is empty")
        if not extracted or not extracted.get("html"):
            raise FetchError(ERROR_NO_CONTENT, "Fetched content is empty")
        try:
            content = await self._convert(request, rendered_html, extracted)
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

    async def _convert(self, request, rendered_html, extracted):
        polished_html = extracted["html"]
        if request.format == "full_html":
            html = rendered_html
            if request.resource_mode == "omit":
                return remove_resources(html)
            if request.resource_mode == "embed":
                return await embed_html(request.url, html)
            return html

        html = polished_html
        if request.resource_mode == "omit":
            html = remove_resources(html)
        elif request.resource_mode == "embed":
            html = await embed_html(request.url, html)
        if request.format == "html":
            return html
        try:
            markdown = await html_to_markdown(html)
        except Exception:
            markdown = None
        if markdown:
            return markdown
        rendered_html = remove_resources(rendered_html)
        return await html_to_markdown(rendered_html)


async def fetch(request: FetchRequest) -> FetchResult:
    return await FetchPipeline().fetch(request)
