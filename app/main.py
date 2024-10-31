import re
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import subprocess
import os
import json

app = FastAPI()

DATA_FOLDER = "data"


class ClipRequest(BaseModel):
    url: str


@app.post("/clip")
async def clip_url_to_markdown(request: ClipRequest):
    url = request.url
    if not url:
        raise HTTPException(status_code=400, detail="URL is required")

    # Ensure the data directory exists
    os.makedirs(DATA_FOLDER, exist_ok=True)

    try:
        # Call the JavaScript script to get polished HTML and metadata
        result = subprocess.run(
            ["node", "index.mjs", url],
            capture_output=True,
            text=True,
            check=True,
            cwd=os.path.join(
                os.path.dirname(os.path.realpath(__file__)), "readability"
            ),
        )

        # Parse the JSON output from the JavaScript script
        output = json.loads(result.stdout)
        html_content = output["html"]
        metadata = output["metadata"]

        # Generate filename prefix using the title from metadata
        safe_title = re.sub(r"[^\w\-_ ]", "_", metadata["title"]).strip()
        filename_prefix = f"{DATA_FOLDER}/{safe_title}"

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

    except subprocess.CalledProcessError as e:
        raise HTTPException(status_code=500, detail=str(e.stderr))
