import logging
import re
import shutil
from typing import List

from . import util
from .cache import cached
import os
import json
import tempfile
import aiohttp
from playwright.async_api import async_playwright, Page, Route, Request
from playwright_stealth import Stealth
from bs4 import BeautifulSoup


SUPPORTED_FORMATS = {
    "markdown": {
        "file_extension": "md",
        "processor": lambda carnivore, url: carnivore._get_markdown_format(url),
    },
    "html": {
        "file_extension": "html",
        "processor": lambda carnivore, url: carnivore._get_html_format(url),
    },
    "full_html": {
        "file_extension": "full.html",
        "processor": lambda carnivore, url: carnivore._get_full_html_format(url),
    },
    "pdf": {
        "file_extension": "pdf",
        "processor": lambda carnivore, url: carnivore._get_pdf_format(url),
    },
}


BLOCKED_KEYWORDS = [
    "Just a moment...",  # Cloudflare
    "Please complete the security check to access",  # archive.ph
    "We've detected unusual activity from your computer network",  # Bloomberg
    "DataDome Device Check",  # The Wall Street Journal
    "DataDome CAPTCHA",  # The Wall Street Journal
    "Captcha Check",  # hCaptcha
]


USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"  # noqa: B950
EXTRA_HTTP_HEADERS = {
    "Sec-CH-UA": '"Chromium";v="131", "Not_A Brand";v="24"',
    "Accept-Language": "en-US,en;q=0.9",
}


class Carnivore:
    @classmethod
    def setup_arg_parser(cls, parser):
        def comma_separated_list(value):
            return value.split(",")

        parser.add_argument(
            "--output-formats",
            required=True,
            type=comma_separated_list,
            help="Output formats separated by commas",
        )
        parser.add_argument(
            "--output-dir",
            required=True,
            type=str,
            help="Output directory for the processed files",
        )
        parser.add_argument(
            "--chrome-extension-paths",
            type=comma_separated_list,
            help="Paths to Chrome extensions to load",
        )
        parser.add_argument(
            "--zenrows-api-key",
            required=False,
            type=str,
            help="Zenrows API key",
        )
        parser.add_argument(
            "--zenrows-premium-proxies",
            required=False,
            action="store_true",
            help="Enable Zenrows premium proxies",
        )
        parser.add_argument(
            "--zenrows-js-rendering",
            required=False,
            action="store_true",
            help="Enable Zenrows JS rendering",
        )
        parser.add_argument(
            "--oxylabs-user",
            required=False,
            type=str,
            help=(
                "Oxylabs Web scraping API username and password."
                " Format: username:password",
            ),
        )
        parser.add_argument(
            "--oxylabs-js-rendering",
            required=False,
            action="store_true",
            help="Enable Oxylabs JS rendering",
        )

    @classmethod
    def from_args(cls, args):
        return cls(
            args.output_formats,
            args.output_dir,
            args.chrome_extension_paths,
            zenrows_api_key=args.zenrows_api_key,
            zenrows_premium_proxies=args.zenrows_premium_proxies,
            zenrows_js_rendering=args.zenrows_js_rendering,
            oxylabs_user=args.oxylabs_user,
            oxylabs_js_rendering=args.oxylabs_js_rendering,
        )

    def __init__(
        self,
        formats: List[str],
        output_dir: str,
        chrome_extension_paths: List[str] = None,
        zenrows_api_key: str = None,
        zenrows_premium_proxies: bool = False,
        zenrows_js_rendering: bool = False,
        oxylabs_user: str = None,
        oxylabs_js_rendering: bool = False,
    ):
        self.formats = formats
        for format in formats:
            if format not in SUPPORTED_FORMATS:
                raise ValueError(f"Unsupported format: {format}")
        self.output_dir = output_dir
        self.chrome_extension_paths = chrome_extension_paths
        self.zenrows_api_key = zenrows_api_key
        self.zenrows_premium_proxies = zenrows_premium_proxies
        self.zenrows_js_rendering = zenrows_js_rendering
        self.oxylabs_user = oxylabs_user
        self.oxylabs_js_rendering = oxylabs_js_rendering
        if zenrows_api_key and oxylabs_user:
            raise ValueError("Only one of Zenrows and Oxylabs can be used at a time")

        self.progress_callback = None
        self.cache_store = {}

    def set_progress_callback(self, callback):
        # Set a callback function to report progress
        self.progress_callback = callback
        pass

    @cached()
    async def _get_embedded_html(self, url: str, html: str, html_type: str) -> str:
        await self._report_progress(f"Embedding resources of {html_type}")
        # Call monolith to get HTML
        return await util.invoke_command(
            [
                "monolith",
                "-",  # Read HTML from stdin
                "-I",  # Isolate the document
                "-v",  # No video
                "-a",  # No audio
                "-b",  # Base URL
                url,
            ],
            input=html,
            no_stderr_warning=True,
        )

    def _is_blocked(self, status: int, html: str) -> bool:
        if status >= 400 and status != 404:
            return True
        for keyword in BLOCKED_KEYWORDS:
            if keyword in html:
                return True
        return False

    @cached()
    async def _get_unblocked_response_with_zenrows(self, url: str):
        await self._report_progress("Getting unblocked HTML with zenrows")
        async with aiohttp.ClientSession() as session:
            params = {
                "url": url,
                "apikey": self.zenrows_api_key,
                "premium_proxy": "true" if self.zenrows_premium_proxies else "false",
                "js_render": "true" if self.zenrows_js_rendering else "false",
            }
            async with session.get(
                "https://api.zenrows.com/v1/", params=params
            ) as response:
                status = response.status
                body = await response.text()
                await self._report_progress(
                    "Finished getting unblocked HTML with zenrows"
                )
                return status, body

    @cached()
    async def _get_unblocked_response_with_oxylabs(self, url: str) -> str:
        await self._report_progress("Getting unblocked HTML with oxylabs")
        auth = aiohttp.BasicAuth(*self.oxylabs_user.split(":"))
        async with aiohttp.ClientSession(auth=auth) as session:
            body = {
                "source": "universal",
                "url": url,
            }
            if self.oxylabs_js_rendering:
                body["render"] = "html"
            async with session.post(
                "https://realtime.oxylabs.io/v1/queries", json=body
            ) as response:
                response.raise_for_status()
                response_body = await response.json()
                await self._report_progress(
                    "Finished getting unblocked HTML with oxylabs"
                )
                result = response_body["results"][0]
                status_code = result["status_code"]
                if status_code >= 400:
                    return (
                        status_code,
                        f"OxyLabs failed to render the page. Code: {status_code}."
                        " See https://developers.oxylabs.io/scraper-apis/web-scraper-api/response-codes for more information.",  # noqa: B950
                    )
                return status_code, result["content"]

    async def _browser_render_common(self, url: str, page_handler):
        async with Stealth().use_async(async_playwright()) as p:
            chromium_args = []
            if self.chrome_extension_paths:
                load_extension_value = ",".join(self.chrome_extension_paths)
                chromium_args += [
                    "--headless=new",  # https://issues.chromium.org/issues/40894124
                    f"-disable-extensions-except={load_extension_value}",
                    f"--load-extension={load_extension_value}",
                ]
            chrome_data_dir = "/tmp/chrome-data"
            if os.path.exists(chrome_data_dir):
                shutil.rmtree(chrome_data_dir)
            async with await p.chromium.launch_persistent_context(
                chrome_data_dir,
                channel="chromium",
                args=chromium_args,
                # https://github.com/Mattwmaster58/playwright_stealth/issues/9
                user_agent=USER_AGENT,
                extra_http_headers=EXTRA_HTTP_HEADERS,
            ) as context:
                context.set_default_timeout(5 * 60 * 1000)  # 5 minutes
                async with await context.new_page() as page:
                    return await page_handler(page, url)

    @cached()
    async def _get_rendered_html_from_url(self, url: str) -> str:
        await self._report_progress("Rendering URL with browser")

        # Use Playwright and a headless browser to get rendered HTML
        async def page_handler(page: Page, url: str):
            async def handle_route(route: Route, request: Request):
                # Intercept network requests to block resources such as images.
                # Since we use monolith to localize all resources,
                # there's no need to load some resources during rendering stage,
                # which only slows down the rendering and costs more data usage.
                if request.resource_type in ("image", "media", "font"):
                    await route.abort()
                    return
                if request.url == url and request.method == "GET":
                    response = await route.fetch()
                    status = response.status
                    body = await response.text()
                    if self._is_blocked(status, body):
                        if self.zenrows_api_key:
                            (
                                status,
                                body,
                            ) = await self._get_unblocked_response_with_zenrows(url)
                        elif self.oxylabs_user:
                            (
                                status,
                                body,
                            ) = await self._get_unblocked_response_with_oxylabs(url)
                    await route.fulfill(
                        status=status,
                        content_type="text/html",
                        body=body,
                    )
                    return
                await route.continue_()

            await page.route("**/*", handle_route)
            response = await page.goto(url)
            status_code = response.status if response else 0
            await page.wait_for_load_state("networkidle")
            html = await page.content()
            if status_code >= 400:
                raise Exception(f"Failed to render URL. Status code: {response.status}")
            if not html:
                raise Exception("Failed to get rendered HTML. Empty HTML.")
            return html

        return await self._browser_render_common(url, page_handler)

    @cached()
    async def _get_polished_data(self, html: str):
        await self._report_progress("Polishing HTML")
        # Call readability to get polished HTML and metadata
        output = await util.invoke_command(
            ["node", "index.mjs"],
            html,
            cwd=os.path.join(
                os.path.dirname(os.path.realpath(__file__)), "readability"
            ),
        )
        return json.loads(output)

    @cached()
    async def _get_markdown(self, html: str, html_type: str):
        await self._report_progress(f"Converting HTML to Markdown with {html_type}")
        # Convert HTML to Markdown using pandoc
        return await util.invoke_command(
            [
                "pandoc",
                "-f",
                "html",
                "-t",
                "gfm-raw_html",
                "--wrap=none",
            ],
            html,
        )

    @cached()
    async def _get_pdf_from_html(self, html: str) -> bytes:
        await self._report_progress("Converting HTML to PDF")

        # Remove loading="lazy" attributes from all img tags
        soup = BeautifulSoup(html, "html.parser")
        for img in soup.find_all("img", loading="lazy"):
            del img["loading"]
        html = str(soup)

        with tempfile.NamedTemporaryFile(suffix=".html", mode="w") as temp_file:
            temp_file.write(html)

            # Use Playwright and a headless browser to get PDF
            async def page_handler(page, url):
                await page.emulate_media(media="print")
                await page.goto("file://" + temp_file.name)
                return await page.pdf()

            return await self._browser_render_common(
                "file://" + temp_file.name, page_handler
            )

    async def _report_progress(self, message: str):
        if self.progress_callback:
            await self.progress_callback(message)

    def _sanitize_file_name(self, file_name: str) -> str:
        base_file_name = re.sub(r'[<>:"/\\|?*]', "-", file_name)
        base_file_name = re.sub(r"\s+", " ", base_file_name)
        base_file_name = base_file_name.strip()
        if not base_file_name:
            base_file_name = "untitled"
        if len(base_file_name) > 128:
            base_file_name = base_file_name[:125] + "..."
        return base_file_name

    async def _get_html_format(self, url: str):
        # Render the URL with a browser before processing with monolith
        # to fix parsing of web pages whose article content is loaded by JavaScript.
        # e.g. https://battleda.sh/blog/ea-account-takeover
        rendered_html = await self._get_rendered_html_from_url(url)
        polished_output = await self._get_polished_data(rendered_html)
        polished_html = polished_output["html"]
        return await self._get_embedded_html(url, polished_html, "polished HTML")

    async def _get_full_html_format(self, url: str):
        rendered_html = await self._get_rendered_html_from_url(url)
        return await self._get_embedded_html(url, rendered_html, "rendered HTML")

    async def _get_markdown_format(self, url: str):
        rendered_html = await self._get_rendered_html_from_url(url)
        polished_output = await self._get_polished_data(rendered_html)
        polished_html = polished_output["html"]
        embedded_html = await self._get_embedded_html(
            url, polished_html, "polished HTML"
        )
        # Convert HTML to Markdown using pandoc
        markdown = None
        for html_type, html in [
            ("embedded HTML", embedded_html),
            ("polished HTML", polished_html),
            ("rendered HTML", rendered_html),
        ]:
            if html:
                try:
                    markdown = await self._get_markdown(html, html_type)
                    if markdown:
                        break
                except Exception as e:
                    logging.exception(
                        f"Failed to convert HTML to Markdown with {html_type}", e
                    )
        if not markdown:
            raise Exception("Failed to convert HTML to Markdown")
        return markdown

    async def _get_pdf_format(self, url: str):
        full_html = await self._get_full_html_format(url)
        return await self._get_pdf_from_html(full_html)

    async def archive(self, url: str):
        async def _get_metadata():
            rendered_html = await self._get_rendered_html_from_url(url)
            polished_output = await self._get_polished_data(rendered_html)
            return polished_output["metadata"]

        metadata = await _get_metadata()
        result = {
            "metadata": {
                **metadata,
                "url": url,
            },
            "files": {},
        }

        file_name = self._sanitize_file_name(metadata["title"])
        for format in self.formats:
            format_spec = SUPPORTED_FORMATS[format]
            try:
                format_content = await format_spec["processor"](self, url)
            except Exception as e:
                if hasattr(e, "message"):
                    message = e.message
                else:
                    message = str(e)
                await self._report_progress(f"Failed to get {format} format: {message}")
                continue
            if not format_content:
                await self._report_progress(
                    f"Failed to get {format} format: content is empty"
                )
                continue
            os.makedirs(self.output_dir, exist_ok=True)
            output_file_path = os.path.join(
                self.output_dir,
                f"{file_name}.{format_spec['file_extension']}",
            )
            if isinstance(format_content, str):
                with open(output_file_path, "w") as f:
                    f.write(format_content)
            elif isinstance(format_content, bytes):
                with open(output_file_path, "wb") as f:
                    f.write(format_content)
            else:
                raise ValueError(
                    "Unsupported format content data type:" f" {type(format_content)}"
                )
            result["files"][format] = output_file_path
        return result
