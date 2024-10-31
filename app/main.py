from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import os
import datetime
import uuid
import trafilatura

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

    # Generate human-readable timestamp
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

    # Generate filename prefix using the timestamp
    filename_prefix = f"{DATA_FOLDER}/{timestamp}_{uuid.uuid4().hex[:4]}"

    # Define filenames
    markdown_filename = f"{filename_prefix}.md"

    try:
        # Fetch HTML content using Trafilatura
        html_content = trafilatura.fetch_url(url)
        if html_content is None:
            raise HTTPException(
                status_code=500, detail="Failed to fetch the URL content"
            )

        # Convert HTML to Markdown using Trafilatura with links and images preserved
        markdown_content = trafilatura.extract(
            html_content,
            output_format="markdown",
            include_links=True,
            include_images=True,
        )

        # Write the Markdown content to a file
        with open(markdown_filename, "w", encoding="utf-8") as file:
            file.write(markdown_content)

        return {"markdown_file": markdown_filename}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
