import logging
import common
import os
import json
import argparse
from playwright.sync_api import sync_playwright


def get_full_html(url: str, html: str) -> str:
    # Call monolith to get HTML
    return common.invoke_command(
        ["monolith", "-", "-I", "-v", "-b", url], input=html, no_stderr_warning=True
    )


def get_rendered_html_from_url(url: str) -> str:
    # Use Playwright and a headless browser to get rendered HTML
    with sync_playwright() as p:
        browser = p.firefox.launch(headless=True)
        try:
            page = browser.new_page()
            page.goto(url)
            return page.content()
        finally:
            browser.close()


def get_polished_data(html: str):
    # Call readability to get polished HTML and metadata
    output = common.invoke_command(
        ["node", "index.mjs"],
        html,
        cwd=os.path.join(os.path.dirname(os.path.realpath(__file__)), "readability"),
    )
    return json.loads(output)


def get_markdown(html: str):
    # Convert HTML to Markdown using pandoc
    return common.invoke_command(
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


def archive(url: str):
    # Render the URL with a browser before processing with monolith
    # to fix parsing of web pages whose article content is loaded by JavaScript.
    # e.g. https://battleda.sh/blog/ea-account-takeover
    rendered_html = get_rendered_html_from_url(url)
    full_html = get_full_html(url, rendered_html)
    polished_output = get_polished_data(full_html)
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
                markdown = get_markdown(html)
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

    result = archive(args.url)
    print(json.dumps(result))
