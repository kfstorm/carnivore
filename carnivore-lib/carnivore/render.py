"""Secure, bounded browser rendering for the single fetch pipeline.

This module owns the browser and network policy for rendering untrusted
pages: scheme and address-space enforcement on every navigation hop,
bounded redirects and resources, a temporary isolated profile, a single
top-level page, and a fixed settle window.
"""

import asyncio
import ipaddress
import shutil
import socket
import tempfile
from dataclasses import dataclass, field
from urllib.parse import urljoin, urlsplit

from playwright.async_api import TimeoutError as PlaywrightTimeoutError
from playwright.async_api import async_playwright

from .models import (
    ERROR_HTTP,
    ERROR_INVALID_INPUT,
    ERROR_NETWORK,
    ERROR_POLICY,
    ERROR_RESOURCE,
    ERROR_TIMEOUT,
    FetchError,
)

SETTLE_WINDOW_SECONDS = 2.0
MAX_REDIRECTS = 10
MAX_MAIN_DOCUMENT_BYTES = 10 * 1024 * 1024
MAX_DOM_BYTES = 10 * 1024 * 1024
MAX_SUBRESOURCE_REQUESTS = 200
MAX_TRANSFER_BYTES = 50 * 1024 * 1024
MAX_OUTPUT_BYTES = 10 * 1024 * 1024

REDIRECT_STATUSES = frozenset((300, 301, 302, 303, 307, 308))
SKIPPED_RESOURCE_TYPES = frozenset(("image", "media", "font"))

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
    " (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)
EXTRA_HTTP_HEADERS = {
    "Sec-CH-UA": '"Chromium";v="131", "Not_A Brand";v="24"',
    "Accept-Language": "en-US,en;q=0.9",
}


def _host_is_loopback(host: str) -> bool:
    host = (host or "").strip("[]").lower()
    if host == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def _address_allowed(address: str, allow_loopback: bool) -> bool:
    parsed = ipaddress.ip_address(address)
    if parsed.is_loopback:
        return allow_loopback
    return parsed.is_global


async def _resolve_host(host: str) -> list[str]:
    loop = asyncio.get_running_loop()
    try:
        infos = await loop.getaddrinfo(host, None, type=socket.SOCK_STREAM)
    except OSError:
        return []
    return [info[4][0] for info in infos]


@dataclass
class RenderPolicy:
    """Tracks and enforces the bounded-rendering security policy."""

    allow_loopback: bool
    redirect_count: int = 0
    subrequest_count: int = 0
    transfer_bytes: int = 0
    error: FetchError | None = None
    _resolve_cache: dict[str, bool] = field(default_factory=dict)

    def fail(self, code: str, message: str) -> None:
        if self.error is None:
            self.error = FetchError(code, message)

    async def check_navigation_url(self, url: str) -> None:
        parsed = urlsplit(url)
        if parsed.scheme not in ("http", "https") or not parsed.netloc:
            self.fail(ERROR_POLICY, "Navigation outside HTTP(S)")
            return
        if not await self._host_allowed(parsed.hostname):
            self.fail(ERROR_POLICY, "Address outside allowed address space")

    async def _host_allowed(self, host: str) -> bool:
        key = (host or "").lower()
        if key not in self._resolve_cache:
            addresses = await _resolve_host(key)
            self._resolve_cache[key] = any(
                _address_allowed(address, self.allow_loopback) for address in addresses
            )
        return self._resolve_cache[key]

    def check_redirect(self) -> None:
        self.redirect_count += 1
        if self.redirect_count > MAX_REDIRECTS:
            self.fail(ERROR_POLICY, "Too many redirects")

    def check_subrequest(self) -> None:
        self.subrequest_count += 1
        if self.subrequest_count > MAX_SUBRESOURCE_REQUESTS:
            self.fail(ERROR_RESOURCE, "Too many subresource requests")

    def add_transfer(self, size: int) -> None:
        self.transfer_bytes += size
        if self.transfer_bytes > MAX_TRANSFER_BYTES:
            self.fail(ERROR_RESOURCE, "Transfer limit exceeded")

    def check_document(self, body: str) -> None:
        if len(body.encode("utf-8")) > MAX_MAIN_DOCUMENT_BYTES:
            self.fail(ERROR_RESOURCE, "Main document too large")

    def check_dom(self, html: str) -> None:
        if len(html.encode("utf-8")) > MAX_DOM_BYTES:
            self.fail(ERROR_RESOURCE, "DOM too large")


def _is_main_document(request, page) -> bool:
    return request.is_navigation_request() and request.frame == page.main_frame


def _inject_base_href(html: str, final_url: str) -> str:
    parsed = urlsplit(final_url)
    href = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
    return html.replace("<head>", f'<head><base href="{href}">', 1)


async def _handle_main_navigation(route, request, policy: RenderPolicy) -> None:
    current_url = request.url
    final_url = current_url
    response = None
    for _ in range(MAX_REDIRECTS + 1):
        await policy.check_navigation_url(current_url)
        if policy.error is not None:
            await route.abort()
            return
        response = await route.fetch(url=current_url, max_redirects=0)
        status = response.status
        location = response.headers.get("location")
        if status in REDIRECT_STATUSES and location:
            policy.check_redirect()
            if policy.error is not None:
                await route.abort()
                return
            current_url = urljoin(current_url, location)
            continue
        final_url = current_url
        break
    body = await response.text()
    policy.check_document(body)
    if policy.error is not None:
        await route.abort()
        return
    if status >= 400:
        policy.fail(ERROR_HTTP, f"HTTP status {status}")
    if final_url != request.url:
        body = _inject_base_href(body, final_url)
    await route.fulfill(status=status, content_type="text/html", body=body)


async def _handle_subresource(route, request, policy: RenderPolicy) -> None:
    parsed = urlsplit(request.url)
    if parsed.scheme not in ("http", "https"):
        await route.abort()
        return
    policy.check_subrequest()
    if policy.error is not None:
        await route.abort()
        return
    response = await route.fetch()
    body = await response.body()
    policy.add_transfer(len(body))
    if policy.error is not None:
        await route.abort()
        return
    await route.fulfill(response=response)


def _make_route_handler(page, policy: RenderPolicy):
    async def handle_route(route, request):
        if policy.error is not None:
            await _safe_abort(route)
            return
        try:
            if _is_main_document(request, page):
                await _handle_main_navigation(route, request, policy)
            elif request.resource_type in SKIPPED_RESOURCE_TYPES:
                await _safe_abort(route)
            else:
                await _handle_subresource(route, request, policy)
        except Exception:
            await _safe_abort(route)

    return handle_route


async def _safe_abort(route) -> None:
    try:
        await route.abort()
    except Exception:
        pass


def _bind_rejections(context) -> None:
    async def reject_new_page(page):
        try:
            await page.close()
        except Exception:
            pass

    async def reject_download(download):
        try:
            await download.cancel()
        except Exception:
            pass

    context.on("page", lambda page: asyncio.create_task(reject_new_page(page)))
    context.on(
        "download", lambda download: asyncio.create_task(reject_download(download))
    )


async def render_browser(url: str, timeout: float) -> str:
    """Render a single URL under the bounded browser policy.

    Returns the DOM snapshot taken after DOMContentLoaded plus the fixed
    settle window. Raises a stable ``FetchError`` for policy and resource
    boundary violations.
    """
    parsed = urlsplit(url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise FetchError(ERROR_INVALID_INPUT, "URL must be an absolute HTTP(S) URL")
    allow_loopback = _host_is_loopback(parsed.hostname)
    policy = RenderPolicy(allow_loopback=allow_loopback)
    profile_dir = tempfile.mkdtemp(prefix="carnivore-render-")
    navigation_timeout_ms = int(max(0.2, timeout - 0.5) * 1000)
    try:
        async with async_playwright() as playwright:
            context = await playwright.chromium.launch_persistent_context(
                profile_dir,
                channel="chromium",
                user_agent=USER_AGENT,
                extra_http_headers=EXTRA_HTTP_HEADERS,
                # Host-local services commonly use private certificates; public URLs
                # keep Chromium's normal certificate validation.
                ignore_https_errors=allow_loopback,
            )
            try:
                page = context.pages[0]
                _bind_rejections(context)
                await page.route("**/*", _make_route_handler(page, policy))
                try:
                    await page.goto(
                        url,
                        wait_until="domcontentloaded",
                        timeout=navigation_timeout_ms,
                    )
                    await asyncio.sleep(SETTLE_WINDOW_SECONDS)
                    rendered = await page.content()
                except PlaywrightTimeoutError:
                    raise FetchError(
                        ERROR_TIMEOUT, f"Timed out after {timeout} seconds"
                    )
                except (asyncio.TimeoutError, asyncio.CancelledError):
                    raise
                except Exception:
                    if policy.error is not None:
                        raise policy.error
                    raise FetchError(ERROR_NETWORK, "Navigation failed")
            finally:
                try:
                    await asyncio.wait_for(context.close(), timeout=5)
                except Exception:
                    pass
    finally:
        shutil.rmtree(profile_dir, ignore_errors=True)
    if policy.error is not None:
        raise policy.error
    policy.check_dom(rendered)
    if policy.error is not None:
        raise policy.error
    return rendered
