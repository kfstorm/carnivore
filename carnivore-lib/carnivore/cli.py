import argparse
import asyncio
import io
import json
import sys

from ruamel.yaml import YAML

from .models import (
    ERROR_INTERNAL,
    ERROR_INVALID_INPUT,
    FetchError,
    FetchRequest,
)
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
    parser.add_argument("--format", default="markdown")
    parser.add_argument("--output", default="raw")
    parser.add_argument("--resource-mode", default="omit")
    parser.add_argument(
        "--timeout",
        type=float,
        default=30.0,
        help="End-to-end fetch budget in seconds",
    )
    return parser


async def main(argv=None) -> int:
    args = _parser().parse_args(argv)
    if args.output not in ("raw", "json"):
        return _report_error(
            FetchError(ERROR_INVALID_INPUT, "Unsupported output mode"), args.output
        )
    try:
        result = await fetch(
            FetchRequest(
                url=args.url,
                format=args.format,
                resource_mode=args.resource_mode,
                timeout=args.timeout,
            )
        )
    except FetchError as error:
        return _report_error(error, args.output)
    except Exception:
        return _report_error(FetchError(ERROR_INTERNAL), args.output)

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


def _report_error(error: FetchError, output: str) -> int:
    if output == "json":
        print(
            json.dumps(
                {
                    "ok": False,
                    "error": {"code": error.code, "detail": error.message},
                },
                ensure_ascii=False,
            )
        )
    else:
        print(error, file=sys.stderr)
    return 2 if error.code == ERROR_INVALID_INPUT else 1


def run(argv=None) -> int:
    return asyncio.run(main(argv))
