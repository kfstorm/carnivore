import asyncio
import logging
from typing import List
from . import util
from .cache import cached
import os
import json
from playwright.async_api import async_playwright


class Carnivore:
    def __init__(self, formats: List[str]):
        self.formats = formats
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

    @cached()
    async def _get_rendered_html_from_url(self, url: str) -> str:
        await self._report_progress("Rendering URL with browser")
        # Use Playwright and a headless browser to get rendered HTML
        async with async_playwright() as p:
            browser = await p.firefox.launch(headless=True)
            try:
                page = await browser.new_page()
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
                content = await page.content()
                await browser.close()
                return content
            finally:
                await browser.close()

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

    async def _report_progress(self, message: str):
        if self.progress_callback:
            await self.progress_callback(message)

    async def archive(self, url: str):
        async def _get_metadata():
            rendered_html = await self._get_rendered_html_from_url(url)
            polished_output = await self._get_polished_data(rendered_html)
            return polished_output["metadata"]

        async def _get_html_format():
            # Render the URL with a browser before processing with monolith
            # to fix parsing of web pages whose article content is loaded by JavaScript.
            # e.g. https://battleda.sh/blog/ea-account-takeover
            rendered_html = await self._get_rendered_html_from_url(url)
            polished_output = await self._get_polished_data(rendered_html)
            polished_html = polished_output["html"]
            return await self._get_embedded_html(url, polished_html, "polished HTML")

        async def _get_full_html_format():
            rendered_html = await self._get_rendered_html_from_url(url)
            return await self._get_embedded_html(url, rendered_html, "rendered HTML")

        async def _get_markdown_format():
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

        metadata = await _get_metadata()
        result = {
            "metadata": {
                **metadata,
                "url": url,
            },
            "content": {},
        }

        format_to_func = {
            "html": _get_html_format,
            "full_html": _get_full_html_format,
            "markdown": _get_markdown_format,
        }
        for format in self.formats:
            if format in format_to_func:
                format_content = await format_to_func[format]()
                if format_content:
                    result["content"][format] = format_content
            else:
                raise ValueError(f"Unsupported format: {format}")
        return result
