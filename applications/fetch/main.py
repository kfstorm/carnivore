import argparse
import asyncio
import io
import json
import logging
import sys

from ruamel.yaml import YAML

import carnivore


SUPPORTED_FETCH_FORMATS = [
    format for format in carnivore.SUPPORTED_FORMATS if format != "pdf"
]


def _metadata_without_empty_values(metadata: dict) -> dict:
    return {key: value for key, value in metadata.items() if value not in (None, "")}


def _add_frontmatter(content: str, metadata: dict) -> str:
    stream = io.StringIO()
    stream.write("---\n")
    yaml = YAML()
    yaml.dump(_metadata_without_empty_values(metadata), stream)
    stream.write("---\n\n")
    stream.write(content)
    return stream.getvalue()


def _build_json_output(result: dict, output: str) -> dict:
    return {
        **_metadata_without_empty_values(result["metadata"]),
        "format": result["format"],
        "output": output,
        "content": result["content"],
    }


async def main():
    parser = argparse.ArgumentParser(description="Fetch readable web content")
    parser.add_argument("url", type=str, help="URL to fetch")
    parser.add_argument(
        "--format",
        choices=SUPPORTED_FETCH_FORMATS,
        default="markdown",
        help="Extracted content format",
    )
    parser.add_argument(
        "--output",
        choices=["raw", "json"],
        default="raw",
        help="CLI output mode",
    )
    parser.add_argument(
        "--post-process-command",
        required=False,
        type=str,
        help="Ignored compatibility argument",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print progress logs to stderr",
    )
    carnivore.Carnivore.setup_arg_parser(parser)
    args = parser.parse_args()

    async def print_progress(message: str):
        print(message, file=sys.stderr)

    try:
        if args.verbose:
            logging.basicConfig(level=logging.INFO)
        else:
            logging.disable(logging.CRITICAL)
        client = carnivore.Carnivore.from_args(args)
        if args.verbose:
            client.set_progress_callback(print_progress)
        result = await client.fetch(args.url, args.format)
        if args.output == "json":
            print(json.dumps(_build_json_output(result, args.output), ensure_ascii=False))
            return
        content = result["content"]
        if args.format == "markdown":
            content = _add_frontmatter(content, result["metadata"])
        print(content, end="")
    except Exception as error:
        print(f"Failed to fetch URL: {error}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
