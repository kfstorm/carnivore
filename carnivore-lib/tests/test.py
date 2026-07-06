import argparse
import base64
import os
import subprocess
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
                    <p>This local article has enough text for readability to parse it as primary content. It includes a small image served by the same test HTTP server so the e2e test can verify whether resources stay linked or become embedded data URLs.</p>
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


def test_entrypoint_passes_resource_mode_env(tmp_path):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    args_file = tmp_path / "args.txt"
    python_path = bin_dir / "python"
    python_path.write_text(
        "#!/usr/bin/env bash\n"
        "printf '%s\n' \"$@\" > \"${CARNIVORE_TEST_ARGS_FILE}\"\n"
    )
    python_path.chmod(0o755)
    env = {
        **os.environ,
        "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}",
        "CARNIVORE_TEST_ARGS_FILE": str(args_file),
        "CARNIVORE_APPLICATION": "fetch",
        "CARNIVORE_RESOURCE_MODE": "embed",
    }

    subprocess.run(["./entrypoint.sh", "https://example.com"], check=True, env=env)

    args = args_file.read_text().splitlines()
    assert args[0] == "applications/fetch/main.py"
    assert args[args.index("--resource-mode") + 1] == "embed"


def test_fetch_wrapper_passes_resource_mode_env(tmp_path):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    args_file = tmp_path / "args.txt"
    docker_path = bin_dir / "docker"
    docker_path.write_text(
        "#!/usr/bin/env bash\n"
        "printf '%s\n' \"$@\" > \"${CARNIVORE_TEST_ARGS_FILE}\"\n"
    )
    docker_path.chmod(0o755)
    env = {
        **os.environ,
        "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}",
        "CARNIVORE_TEST_ARGS_FILE": str(args_file),
        "CARNIVORE_CACHE": "0",
        "CARNIVORE_RESOURCE_MODE": "link",
    }

    subprocess.run(
        ["skills/carnivore-fetch/bin/carnivore-fetch", "https://example.com"],
        check=True,
        env=env,
    )

    args = args_file.read_text().splitlines()
    assert args[0] == "run"
    assert args[args.index("-e") + 1] == "CARNIVORE_APPLICATION=fetch"
    assert "CARNIVORE_RESOURCE_MODE" in args


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


def test_cli_resource_mode_omits_by_default():
    client = carnivore.Carnivore.from_args(_parse_carnivore_args())

    assert client.resource_mode == "omit"


def test_cli_resource_mode_can_link():
    client = carnivore.Carnivore.from_args(
        _parse_carnivore_args("--resource-mode", "link")
    )

    assert client.resource_mode == "link"


def test_cli_resource_mode_can_embed():
    client = carnivore.Carnivore.from_args(
        _parse_carnivore_args("--resource-mode", "embed")
    )

    assert client.resource_mode == "embed"


@pytest.mark.asyncio
async def test_default_outputs_omit_resources(monkeypatch):
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
    assert "image.jpg" not in html
    assert "image.jpg" not in full_html
    assert "image.jpg" not in markdown
    assert len(markdown) < 1000


@pytest.mark.asyncio
async def test_link_resource_mode_keeps_resource_links(monkeypatch):
    client = carnivore.Carnivore(
        carnivore.SUPPORTED_FORMATS,
        "data",
        resource_mode="link",
    )

    async def get_embedded_html(url, html, html_type):
        return html + '<img src="data:image/png;base64,aaaa">'

    html, full_html, markdown = await _get_stubbed_outputs(
        monkeypatch,
        client,
        get_embedded_html,
    )

    assert "data:image" not in html
    assert "data:image" not in full_html
    assert "data:image" not in markdown
    assert "image.jpg" in html
    assert "image.jpg" in full_html
    assert "image.jpg" in markdown


@pytest.mark.asyncio
async def test_embed_resource_mode_uses_embedded_html(monkeypatch):
    client = carnivore.Carnivore(
        carnivore.SUPPORTED_FORMATS,
        "data",
        resource_mode="embed",
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
async def test_outputs_e2e_handle_images_by_resource_mode(local_image_page_url):
    default_client = carnivore.Carnivore(["full_html"], "data")
    link_client = carnivore.Carnivore(
        ["full_html"],
        "data",
        resource_mode="link",
    )
    embed_client = carnivore.Carnivore(
        ["full_html"],
        "data",
        resource_mode="embed",
    )

    default_full_html = await default_client._get_full_html_format(local_image_page_url)
    link_full_html = await link_client._get_full_html_format(local_image_page_url)
    embedded_full_html = await embed_client._get_full_html_format(local_image_page_url)

    assert "data:image" not in default_full_html
    assert "/pixel.png" not in default_full_html
    assert "data:image" not in link_full_html
    assert "/pixel.png" in link_full_html
    assert "data:image/png;base64" in embedded_full_html
    assert "/pixel.png" not in embedded_full_html

    default_markdown = await default_client._get_markdown_format(local_image_page_url)
    link_markdown = await link_client._get_markdown_format(local_image_page_url)
    embedded_markdown = await embed_client._get_markdown_format(local_image_page_url)

    assert "data:image" not in default_markdown
    assert "/pixel.png" not in default_markdown
    assert "data:image" not in link_markdown
    assert "/pixel.png" in link_markdown
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
    link_instance = carnivore.Carnivore(
        carnivore.SUPPORTED_FORMATS,
        "data",
        resource_mode="link",
    )
    embed_instance = carnivore.Carnivore(
        carnivore.SUPPORTED_FORMATS,
        "data",
        resource_mode="embed",
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
    link_key = _generate_key(
        "_get_rendered_html_from_url",
        args,
        {},
        link_instance.get_cache_namespace(),
    )
    embed_key = _generate_key(
        "_get_rendered_html_from_url",
        args,
        {},
        embed_instance.get_cache_namespace(),
    )

    assert len({default_key, zenrows_key, oxylabs_key, link_key, embed_key}) == 5
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
