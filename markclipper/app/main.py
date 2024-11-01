import re
import subprocess
import os
import json
import argparse
import datetime
import uuid


def invoke_command(command: list[str], input: str = None, **kwargs) -> str:
    # Invoke a command and return the output
    process = subprocess.Popen(
        command,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        **kwargs,
    )
    stdout, stderr = process.communicate(input=input.encode() if input else None)
    if process.returncode != 0:
        raise Exception(
            f"subprocess of command {command} failed with exit code {process.returncode}: {stderr.decode()}"
        )
    return stdout.decode()


def get_html(url: str) -> str:
    # Call monolith to get HTML
    return invoke_command(["monolith", "-v", url])


def get_polished_data(html: str):
    # Call the JavaScript script to get polished HTML and metadata
    output = invoke_command(
        ["node", "index.mjs"],
        html,
        cwd=os.path.join(os.path.dirname(os.path.realpath(__file__)), "readability"),
    )
    return json.loads(output)


def get_markdown(html: str):
    # Convert HTML to Markdown using pandoc
    return invoke_command(
        [
            "pandoc",
            "-t",
            "gfm-raw_html",
            "--wrap=none",
        ],
        html,
    )


def clip_url_to_markdown(args: argparse.Namespace):
    full_html = get_html(args.url)
    # Parse the JSON output from the JavaScript script
    output = get_polished_data(full_html)
    html = output["html"]
    metadata = output["metadata"]

    # Convert HTML to Markdown using pandoc
    markdown = get_markdown(html)

    return {
        "metadata": metadata,
        "content": {
            "markdown": markdown,
            "html": html,
            "full_html": full_html,
        },
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Clip a URL to Markdown")
    parser.add_argument(
        "--url",
        "-u",
        type=str,
        required=True,
        help="The URL to clip",
    )
    args = parser.parse_args()

    result = clip_url_to_markdown(args)
    print(json.dumps(result))
