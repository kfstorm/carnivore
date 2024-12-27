import asyncio
import logging
import re
import time
from typing import List

from . import util
from .cache import cached
import os
import json
import tempfile
import aiohttp
from playwright.async_api import async_playwright
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

    @classmethod
    def from_args(cls, args):
        return cls(
            args.output_formats,
            args.output_dir,
            zenrows_api_key=args.zenrows_api_key,
            zenrows_premium_proxies=args.zenrows_premium_proxies,
            zenrows_js_rendering=args.zenrows_js_rendering,
        )

    def __init__(
        self,
        formats: List[str],
        output_dir: str,
        zenrows_api_key: str = None,
        zenrows_premium_proxies: bool = False,
        zenrows_js_rendering: bool = False,
    ):
        self.formats = formats
        for format in formats:
            if format not in SUPPORTED_FORMATS:
                raise ValueError(f"Unsupported format: {format}")
        self.output_dir = output_dir
        self.zenrows_api_key = zenrows_api_key
        self.zenrows_premium_proxies = zenrows_premium_proxies
        self.zenrows_js_rendering = zenrows_js_rendering
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
            ["monolith", "-", "-I", "-v", "-b", url],
            input=html,
            no_stderr_warning=True,
        )

    def _is_blocked(self, html: str) -> bool:
        return "Just a moment..." in html

    @cached()
    async def _get_rendered_html_from_zenrows(self, url: str) -> str:
        await self._report_progress("Rendering URL with zenrows")
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
                return await response.text()

    async def _browser_render_common(self, url: str, page_handler):
        async with Stealth().use_async(async_playwright()) as p:
            browser = await p.chromium.launch()
            async with await browser.new_context() as context:
                async with await context.new_page() as page:
                    return await page_handler(page, url)

    @cached()
    async def _get_rendered_html_from_url(self, url: str) -> str:
        await self._report_progress("Rendering URL with browser")

        # Use Playwright and a headless browser to get rendered HTML
        async def page_handler(page, url):
            # Intercept network requests to block resources such as images.
            # Since we use monolith to localize all resources,
            # there's no need to load some resources during rendering stage,
            # which only slows down the rendering and costs more data usage.
            await page.route(
                "**/*",
                lambda route, request: (
                    asyncio.create_task(route.abort())
                    if request.resource_type in ("image", "media", "font")
                    else asyncio.create_task(route.continue_())
                ),
            )
            await page.goto(url)
            await page.wait_for_load_state("networkidle")
            html = await page.content()
            max_wait_time = 10
            now = time.time()
            while self._is_blocked(html):
                await asyncio.sleep(1)
                await page.wait_for_load_state("networkidle")
                html = await page.content()
                if time.time() - now > max_wait_time:
                    break
            if self._is_blocked(html) and self.zenrows_api_key:
                html = await self._get_rendered_html_from_zenrows(url)
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
