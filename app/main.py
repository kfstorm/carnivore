import re
import subprocess
import os
import json
import argparse


def clip_url_to_markdown(url: str, output_dir: str):
    # Ensure the data directory exists
    os.makedirs(output_dir, exist_ok=True)

    # Call the JavaScript script to get polished HTML and metadata
    result = subprocess.run(
        ["node", "index.mjs", url],
        capture_output=True,
        text=True,
        check=True,
        cwd=os.path.join(os.path.dirname(os.path.realpath(__file__)), "readability"),
    )

    # Parse the JSON output from the JavaScript script
    output = json.loads(result.stdout)
    html_content = output["html"]
    metadata = output["metadata"]

    # Generate filename prefix using the title from metadata
    safe_title = re.sub(r"[^\w\-_ ]", "_", metadata["title"]).strip()
    filename_prefix = f"{output_dir}/{safe_title}"

    # Define filenames
    html_filename = f"{filename_prefix}.html"
    markdown_filename = f"{filename_prefix}.md"
    json_filename = f"{filename_prefix}.json"

    # Write the HTML content to a file
    with open(html_filename, "w", encoding="utf-8") as file:
        file.write(html_content)

    # Write the metadata to a JSON file
    with open(json_filename, "w", encoding="utf-8") as file:
        json.dump(metadata, file, indent=2)

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
    parser.add_argument("--url", "-u", type=str, help="The URL to clip")
    parser.add_argument(
        "--output-dir",
        "-o",
        type=str,
        help="The directory to save the clipped files",
    )
    args = parser.parse_args()

    result = clip_url_to_markdown(args.url, args.output_dir)
    print(json.dumps(result, indent=2))
