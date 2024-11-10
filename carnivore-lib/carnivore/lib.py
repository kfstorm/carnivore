import asyncio
import logging
from . import util
import os
import json
from playwright.async_api import async_playwright


class Carnivore:
    def __init__(self):
        self.progress_callback = None
        pass

    def set_progress_callback(self, callback):
        # Set a callback function to report progress
        self.progress_callback = callback
        pass

    async def _get_full_html(self, url: str, html: str) -> str:
        # Call monolith to get HTML
        return await util.invoke_command(
            ["monolith", "-", "-I", "-v", "-b", url], input=html, no_stderr_warning=True
        )

    async def _get_rendered_html_from_url(self, url: str) -> str:
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
                return await page.content()
            finally:
                await browser.close()

    async def _get_polished_data(self, html: str):
        # Call readability to get polished HTML and metadata
        output = await util.invoke_command(
            ["node", "index.mjs"],
            html,
            cwd=os.path.join(
                os.path.dirname(os.path.realpath(__file__)), "readability"
            ),
        )
        return json.loads(output)

    async def _get_markdown(self, html: str):
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
        # Render the URL with a browser before processing with monolith
        # to fix parsing of web pages whose article content is loaded by JavaScript.
        # e.g. https://battleda.sh/blog/ea-account-takeover
        await self._report_progress("Rendering URL with browser")
        rendered_html = await self._get_rendered_html_from_url(url)
        await self._report_progress("Getting full HTML")
        full_html = await self._get_full_html(url, rendered_html)
        await self._report_progress("Polishing HTML")
        polished_output = await self._get_polished_data(full_html)
        polished_html = polished_output["html"]
        metadata = polished_output["metadata"]

        # Convert HTML to Markdown using pandoc
        markdown = None
        for html_type, html in [
            ("polished HTML", polished_html),
            ("full HTML", full_html),
            ("rendered HTML", rendered_html),
        ]:
            if html:
                try:
                    await self._report_progress(
                        f"Converting HTML to Markdown with {html_type}"
                    )
                    markdown = await self._get_markdown(html)
                    if markdown:
                        break
                except Exception as e:
                    logging.error(
                        f"Failed to convert HTML to Markdown with {html_type}: {str(e)}"
                    )
        if not markdown:
            raise Exception("Failed to convert HTML to Markdown")

        result = {
            "metadata": {
                **metadata,
                "url": url,
            },
            "content": {},
        }
        if full_html:
            result["content"]["full_html"] = full_html
        if rendered_html:
            result["content"]["rendered_html"] = rendered_html
        if polished_html:
            result["content"]["html"] = polished_html
        if markdown:
            result["content"]["markdown"] = markdown
        return result
