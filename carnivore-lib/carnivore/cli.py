import argparse
import asyncio
import io
import json
import sys

from ruamel.yaml import YAML

from .models import FetchRequest, RESOURCE_MODES, SUPPORTED_FORMATS
from .pipeline import fetch


def _frontmatter(metadata: dict, content: str) -> str:
    stream = io.StringIO()
    stream.write("---\n")
    YAML().dump(metadata, stream)
    stream.write("---\n\n")
    stream.write(content)
    return stream.getvalue()


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Fetch readable web content")
    parser.add_argument("url", help="Absolute HTTP(S) URL to fetch")
    parser.add_argument("--format", choices=SUPPORTED_FORMATS, default="markdown")
    parser.add_argument("--output", choices=("raw", "json"), default="raw")
    parser.add_argument("--resource-mode", choices=RESOURCE_MODES, default="omit")
    return parser


async def main(argv=None) -> int:
    args = _parser().parse_args(argv)
    try:
        result = await fetch(
            FetchRequest(
                url=args.url,
                format=args.format,
                resource_mode=args.resource_mode,
            )
        )
    except Exception as error:
        print(f"Failed to fetch URL: {error}", file=sys.stderr)
        return 1

    if args.output == "json":
        print(
            json.dumps(
                {
                    "ok": True,
                    "format": result.format,
                    "content": result.content,
                    "metadata": result.metadata,
                },
                ensure_ascii=False,
            )
        )
    elif result.format == "markdown":
        print(_frontmatter(result.metadata, result.content), end="")
    else:
        print(result.content, end="")
    return 0


def run(argv=None) -> int:
    return asyncio.run(main(argv))
