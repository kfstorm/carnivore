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
        raise Exception(f"subprocess failed with error: {stderr.decode()}")
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


def clip_url_to_markdown(args: argparse.Namespace):
    html = get_html(args.url)
    # Parse the JSON output from the JavaScript script
    output = get_polished_data(html)
    html_content = output["html"]
    metadata = output["metadata"]

    if args.filename_prefix:
        if args.filename_method:
            raise ValueError("Cannot specify both filename prefix and method")
        # Use the provided filename prefix
        filename_prefix = f"{args.output_dir}/{args.filename_prefix}"
    else:
        if not args.filename_method:
            raise ValueError("Filename prefix or method is required")
        if args.filename_method == "title":
            # Generate filename prefix using the title from metadata
            safe_title = re.sub(r"[^\w\-_ ]", "_", metadata["title"]).strip()
            filename_prefix = f"{args.output_dir}/{safe_title}"
        elif args.filename_method == "timestamp":
            # Generate filename prefix based on current timestamp
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            filename_prefix = f"{args.output_dir}/{timestamp}"
        elif args.filename_method == "random":
            # Generate random filename prefix
            filename_prefix = f"{args.output_dir}/{uuid.uuid4().hex}"
        else:
            raise ValueError("Invalid filename method")

    # Define filenames
    full_html_filename = f"{filename_prefix}_full.html"
    html_filename = f"{filename_prefix}.html"
    markdown_filename = f"{filename_prefix}.md"
    json_filename = f"{filename_prefix}.json"

    # Ensure the data directory exists
    os.makedirs(args.output_dir, exist_ok=True)

    # Write the full HTML content to a file
    with open(full_html_filename, "w", encoding="utf-8") as file:
        file.write(html)

    # Write the HTML content to a file
    with open(html_filename, "w", encoding="utf-8") as file:
        file.write(html_content)

    # Write the metadata to a JSON file
    with open(json_filename, "w", encoding="utf-8") as file:
        json.dump(metadata, file, indent=2, ensure_ascii=False)

    # Convert HTML to Markdown using pandoc
    subprocess.run(
        [
            "pandoc",
            html_filename,
            "-t",
            "gfm-raw_html",
            "--wrap=none",
            "-o",
            markdown_filename,
        ],
        check=True,
    )

    return {
        "markdown_file": markdown_filename,
        "html_file": html_filename,
        "full_html_file": full_html_filename,
        "metadata_file": json_filename,
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
    parser.add_argument(
        "--output-dir",
        "-o",
        type=str,
        required=True,
        help="The directory to save the clipped files",
    )
    parser.add_argument(
        "--filename-prefix",
        "-fp",
        type=str,
        help="The prefix for the generated filenames",
    )
    parser.add_argument(
        "--filename-method",
        "-fm",
        choices=["timestamp", "title", "random"],
        help="The method to generate filenames.",
    )
    args = parser.parse_args()

    result = clip_url_to_markdown(args)
    print(json.dumps(result, indent=2, ensure_ascii=False))
