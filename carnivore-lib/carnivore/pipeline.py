import tempfile
from urllib.parse import urlsplit

from .lib import Carnivore
from .models import FetchRequest, FetchResult, RESOURCE_MODES, SUPPORTED_FORMATS


def validate_request(request: FetchRequest) -> None:
    parsed = urlsplit(request.url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise ValueError("URL must be an absolute HTTP(S) URL")
    if request.format not in SUPPORTED_FORMATS:
        raise ValueError(f"Unsupported format: {request.format}")
    if request.resource_mode not in RESOURCE_MODES:
        raise ValueError(f"Unsupported resource mode: {request.resource_mode}")


class FetchPipeline:
    """Coordinate fetch stages behind the public fetch(request) seam."""

    async def fetch(self, request: FetchRequest) -> FetchResult:
        validate_request(request)
        client = Carnivore(
            [request.format],
            tempfile.gettempdir(),
            resource_mode=request.resource_mode,
        )
        rendered_html = await client._get_rendered_html_from_url(request.url)
        extracted = await client._get_polished_data(rendered_html)
        content = await self._convert(client, request, rendered_html, extracted)
        if not content:
            raise ValueError("Fetched content is empty")
        metadata = {
            key: value
            for key, value in extracted.get("metadata", {}).items()
            if value not in (None, "")
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
