import logging
import subprocess
import os
import json
import argparse
import tempfile
from playwright.sync_api import sync_playwright


def invoke_command(
    command: list[str],
    input: str = None,
    redirect_stderr_to_stdout: bool = False,
    **kwargs,
) -> str:
    # Invoke a command and return the output
    process = subprocess.Popen(
        command,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=(subprocess.STDOUT if redirect_stderr_to_stdout else subprocess.PIPE),
        **kwargs,
    )
    stdout, stderr = process.communicate(input=input.encode() if input else None)
    if process.returncode != 0:
        message = (
            f"Subprocess of command {command} failed"
            f" with exit code {process.returncode}."
        )
        if stdout and stderr:
            message += f"\nstderr:\n{stderr.decode()}"
            message += f"\nstdout:\n{stdout.decode()}"
        elif stdout:
            message += f"\n{stdout.decode()}"
        elif stderr:
            message += f"\n{stderr.decode()}"
        raise Exception(message)
    return stdout.decode()


def get_full_html(url: str) -> str:
    # Call monolith to get HTML
    return invoke_command(["monolith", "-v", url])


def get_rendered_html(html: str):
    # Write the HTML to a temp file first
    with tempfile.NamedTemporaryFile(mode="w", suffix=".html") as f:
        f.write(html)
        temp_file = f.name

        # Use Playwright and a headless browser to get rendered HTML
        with sync_playwright() as p:
            browser = p.firefox.launch(headless=True)
            try:
                page = browser.new_page()
                page.goto(f"file://{temp_file}")
                return page.content()
            finally:
                browser.close()


def get_polished_data(html: str):
    # Call readability to get polished HTML and metadata
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
            "-f",
            "html",
            "-t",
            "gfm-raw_html",
            "--wrap=none",
        ],
        html,
    )


def clip_url_to_markdown(args: argparse.Namespace):
    full_html = get_full_html(args.url)
    try:
        rendered_html = get_rendered_html(full_html)
    except Exception as e:
        logging.error(f"Failed to render HTML: {e}")
        rendered_html = None

    polished_html = None
    metadata = {}
    for name, html in [("rendered html", rendered_html), ("full html", full_html)]:
        if html:
            try:
                polished_output = get_polished_data(html)
                polished_html = polished_output["html"]
                metadata = polished_output["metadata"]
                break
            except Exception as e:
                logging.error(f"Failed to get polished data with {name}: {e}")

    # Convert HTML to Markdown using pandoc
    markdown = None
    try:
        markdown = get_markdown(polished_html if polished_html else full_html)
    except Exception as e:
        logging.error(f"Failed to convert HTML to Markdown: {e}")

    result = {
        "metadata": {
            **metadata,
            "url": args.url,
        },
        "content": {
            "full_html": full_html,
        },
    }
    if rendered_html:
        result["content"]["rendered_html"] = rendered_html
    if polished_html:
        result["content"]["html"] = polished_html
    if markdown:
        result["content"]["markdown"] = markdown
    return result


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
