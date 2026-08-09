from bs4 import BeautifulSoup

from .process import invoke_command
from .render import MAX_OUTPUT_BYTES


RESOURCE_TAGS = (
    "img",
    "picture",
    "source",
    "video",
    "audio",
    "iframe",
    "object",
    "embed",
    "svg",
)


def remove_resources(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup.find_all(RESOURCE_TAGS):
        tag.decompose()
    return str(soup)


async def embed_html(url: str, html: str) -> str:
    return await invoke_command(
        [
            "monolith",
            "-",
            "-I",
            "-v",
            "-a",
            "-b",
            url,
        ],
        input=html,
        max_output_bytes=MAX_OUTPUT_BYTES,
    )


async def html_to_markdown(html: str) -> str:
    return await invoke_command(
        [
            "pandoc",
            "-f",
            "html",
            "-t",
            "gfm-raw_html",
            "--wrap=none",
        ],
        input=html,
        max_output_bytes=MAX_OUTPUT_BYTES,
    )
