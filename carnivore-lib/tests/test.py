import argparse
import base64
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread

import pytest
import carnivore
from carnivore.cache import _generate_key

MARKDOWN_MIN_SIZE_WITH_IMAGES = 1000  # Adjust this value as needed
PIXEL_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMBAAZnGfoAAAAASUVORK5CYII="
)


class LocalImagePageHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/pixel.png":
            self.send_response(200)
            self.send_header("Content-Type", "image/png")
            self.send_header("Content-Length", str(len(PIXEL_PNG)))
            self.end_headers()
            self.wfile.write(PIXEL_PNG)
            return

        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(
            b"""
            <!doctype html>
            <html>
              <head><title>Local image page</title></head>
              <body>
                <main>
                  <article>
                    <h1>Local image page</h1>
                    <p>This local article has enough text for readability to parse it as primary content. It includes a small image served by the same test HTTP server so the e2e test can verify whether resources stay external or become embedded data URLs.</p>
                    <p>The page is intentionally self-contained and deterministic. It avoids external network access while still exercising the real browser rendering, readability processing, monolith embedding, and pandoc Markdown conversion paths.</p>
                    <img src=\"/pixel.png\" alt=\"pixel\">
                  </article>
                </main>
              </body>
            </html>
            """
        )

    def log_message(self, format, *args):
        pass


@pytest.fixture
def local_image_page_url():
    server = ThreadingHTTPServer(("127.0.0.1", 0), LocalImagePageHandler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}/"
    finally:
        server.shutdown()
        thread.join()


def _parse_carnivore_args(*extra_args):
    parser = argparse.ArgumentParser()
    carnivore.Carnivore.setup_arg_parser(parser)
    return parser.parse_args(
        [
            "--output-formats",
            "markdown,html,full_html",
            "--output-dir",
            "data",
            *extra_args,
        ]
    )


async def _get_stubbed_outputs(monkeypatch, client, get_embedded_html):
    async def get_rendered_html_from_url(url):
        return '<html><body><article><img src="image.jpg">rendered</article></body></html>'

    async def get_polished_data(html):
        return {
            "html": '<article><img src="image.jpg">polished</article>',
            "metadata": {},
        }

    async def get_markdown(html, html_type):
        return html

    monkeypatch.setattr(client, "_get_rendered_html_from_url", get_rendered_html_from_url)
    monkeypatch.setattr(client, "_get_polished_data", get_polished_data)
    monkeypatch.setattr(client, "_get_embedded_html", get_embedded_html)
    monkeypatch.setattr(client, "_get_markdown", get_markdown)

    return (
        await client._get_html_format("https://example.com"),
        await client._get_full_html_format("https://example.com"),
        await client._get_markdown_format("https://example.com"),
    )


@pytest.fixture(scope="module")
def carnivore_instance():
    instance = carnivore.Carnivore(carnivore.SUPPORTED_FORMATS, "data")

    async def async_print(message: str):
        print(message)

    instance.set_progress_callback(async_print)
    return instance


def file_size_check(file_path, min_size):
    with open(file_path, "rb") as f:
        size = len(f.read())
        assert (
            size >= min_size
        ), f"Content of {file_path} is too small. Size: {size}, expected: >={min_size}"


async def _test_common(
    carnivore_instance, url, markdown_min_size=None, pdf_min_size=None
):
    output = await carnivore_instance.archive(url)
    assert output["metadata"]["title"], "Title not found in output"
    for format in carnivore.SUPPORTED_FORMATS:
        assert output["files"][format], f"{format} content not found in output"
    if markdown_min_size:
        file_size_check(output["files"]["markdown"], markdown_min_size)
    if pdf_min_size:
        file_size_check(output["files"]["pdf"], pdf_min_size)
    return output


def test_cli_embed_resources_disabled_by_default():
    client = carnivore.Carnivore.from_args(_parse_carnivore_args())

    assert client.embed_resources is False


def test_cli_embed_resources_can_be_enabled():
    client = carnivore.Carnivore.from_args(
        _parse_carnivore_args("--embed-resources")
    )

    assert client.embed_resources is True


@pytest.mark.asyncio
async def test_default_outputs_do_not_embed_resources(monkeypatch):
    client = carnivore.Carnivore(carnivore.SUPPORTED_FORMATS, "data")
    embedded_calls = []

    async def get_embedded_html(url, html, html_type):
        embedded_calls.append((url, html, html_type))
        return html + '<img src="data:image/png;base64,' + ("a" * 1000) + '">'

    html, full_html, markdown = await _get_stubbed_outputs(
        monkeypatch,
        client,
        get_embedded_html,
    )

    assert embedded_calls == []
    assert "data:image" not in html
    assert "data:image" not in full_html
    assert "data:image" not in markdown
    assert len(markdown) < 1000


@pytest.mark.asyncio
async def test_embed_resources_enabled_uses_embedded_html(monkeypatch):
    client = carnivore.Carnivore(
        carnivore.SUPPORTED_FORMATS,
        "data",
        embed_resources=True,
    )

    async def get_embedded_html(url, html, html_type):
        return html + '<img src="data:image/png;base64,aaaa">'

    html, full_html, markdown = await _get_stubbed_outputs(
        monkeypatch,
        client,
        get_embedded_html,
    )

    assert "data:image" in html
    assert "data:image" in full_html
    assert "data:image" in markdown


@pytest.mark.asyncio
async def test_outputs_e2e_embed_images_only_when_enabled(local_image_page_url):
    default_client = carnivore.Carnivore(["full_html"], "data")
    embed_client = carnivore.Carnivore(
        ["full_html"],
        "data",
        embed_resources=True,
    )

    default_full_html = await default_client._get_full_html_format(local_image_page_url)
    embedded_full_html = await embed_client._get_full_html_format(local_image_page_url)

    assert "data:image" not in default_full_html
    assert "/pixel.png" in default_full_html
    assert "data:image/png;base64" in embedded_full_html
    assert "/pixel.png" not in embedded_full_html

    default_markdown = await default_client._get_markdown_format(local_image_page_url)
    embedded_markdown = await embed_client._get_markdown_format(local_image_page_url)

    assert "data:image" not in default_markdown
    assert "/pixel.png" in default_markdown
    assert "data:image/png;base64" in embedded_markdown
    assert "/pixel.png" not in embedded_markdown


@pytest.mark.asyncio
async def test_pdf_always_uses_embedded_full_html(monkeypatch):
    client = carnivore.Carnivore(["pdf"], "data")

    async def get_rendered_html_from_url(url):
        return '<html><body><img src="/pixel.png"></body></html>'

    async def get_embedded_html(url, html, html_type):
        return '<html><body><img src="data:image/png;base64,aaaa"></body></html>'

    async def get_pdf_from_html(html):
        return html.encode()

    monkeypatch.setattr(client, "_get_rendered_html_from_url", get_rendered_html_from_url)
    monkeypatch.setattr(client, "_get_embedded_html", get_embedded_html)
    monkeypatch.setattr(client, "_get_pdf_from_html", get_pdf_from_html)

    pdf_input = await client._get_pdf_format("https://example.com")

    assert b"data:image/png;base64" in pdf_input
    assert b"/pixel.png" not in pdf_input


def test_cache_key_includes_runtime_configuration():
    default_instance = carnivore.Carnivore(carnivore.SUPPORTED_FORMATS, "data")
    zenrows_instance = carnivore.Carnivore(
        carnivore.SUPPORTED_FORMATS,
        "data",
        zenrows_api_key="secret-api-key",
        zenrows_premium_proxies=True,
    )
    oxylabs_instance = carnivore.Carnivore(
        carnivore.SUPPORTED_FORMATS,
        "data",
        oxylabs_user="user:secret-password",
        oxylabs_js_rendering=True,
    )
    embed_instance = carnivore.Carnivore(
        carnivore.SUPPORTED_FORMATS,
        "data",
        embed_resources=True,
    )

    args = ("https://example.com",)
    default_key = _generate_key(
        "_get_rendered_html_from_url",
        args,
        {},
        default_instance.get_cache_namespace(),
    )
    zenrows_key = _generate_key(
        "_get_rendered_html_from_url",
        args,
        {},
        zenrows_instance.get_cache_namespace(),
    )
    oxylabs_key = _generate_key(
        "_get_rendered_html_from_url",
        args,
        {},
        oxylabs_instance.get_cache_namespace(),
    )
    embed_key = _generate_key(
        "_get_rendered_html_from_url",
        args,
        {},
        embed_instance.get_cache_namespace(),
    )

    assert len({default_key, zenrows_key, oxylabs_key, embed_key}) == 4
    assert "secret-api-key" not in str(zenrows_instance.get_cache_namespace())
    assert "secret-password" not in str(oxylabs_instance.get_cache_namespace())


@pytest.mark.asyncio
async def test_dynamic_content_loading(carnivore_instance):
    await _test_common(
        carnivore_instance,
        "https://battleda.sh/blog/ea-account-takeover",
        markdown_min_size=MARKDOWN_MIN_SIZE_WITH_IMAGES,
    )


@pytest.mark.asyncio
async def test_visibility_hidden(carnivore_instance):
    await _test_common(
        carnivore_instance,
        "https://mp.weixin.qq.com/s/koaLJvsFLkfi_j3HKIi6Dw",
        markdown_min_size=MARKDOWN_MIN_SIZE_WITH_IMAGES,
    )


@pytest.mark.asyncio
async def test_no_timeout(carnivore_instance):
    await _test_common(
        carnivore_instance,
        "https://jhftss.github.io/A-New-Era-of-macOS-Sandbox-Escapes/",
        markdown_min_size=MARKDOWN_MIN_SIZE_WITH_IMAGES,
    )


@pytest.mark.asyncio
async def test_pdf_images_no_lazy_loading(carnivore_instance):
    await _test_common(
        carnivore_instance,
        "https://www.rfleury.com/p/demystifying-debuggers-part-2-the",
        markdown_min_size=MARKDOWN_MIN_SIZE_WITH_IMAGES,
        pdf_min_size=5 * 1024 * 1024,
    )


@pytest.mark.asyncio
async def test_http_headers(carnivore_instance):
    output = await _test_common(
        carnivore_instance,
        "http://gethttp.info/",
    )
    with open(output["files"]["full_html"], "r") as f:
        html = f.read()
    assert "Headless" not in html


if __name__ == "__main__":
    pytest.main()
