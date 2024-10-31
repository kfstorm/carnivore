import re
import subprocess
import os
import json
import argparse
import datetime
import uuid


def clip_url_to_markdown(args: argparse.Namespace):
    # Ensure the data directory exists
    os.makedirs(args.output_dir, exist_ok=True)

    # Call the JavaScript script to get polished HTML and metadata
    result = subprocess.run(
        ["node", "index.mjs", args.url],
        capture_output=True,
        text=True,
        check=True,
        cwd=os.path.join(os.path.dirname(os.path.realpath(__file__)), "readability"),
    )

    # Parse the JSON output from the JavaScript script
    output = json.loads(result.stdout)
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
    html_filename = f"{filename_prefix}.html"
    markdown_filename = f"{filename_prefix}.md"
    json_filename = f"{filename_prefix}.json"

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
            "gfm",
            "--strip-comments",
            "--wrap=none",
            "-o",
            markdown_filename,
        ],
        check=True,
    )

    return {
        "markdown_file": markdown_filename,
        "html_file": html_filename,
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
