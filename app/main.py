from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import subprocess
import os
import datetime
import uuid

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
    html_filename = f"{filename_prefix}.html"
    markdown_filename = f"{filename_prefix}.md"

    try:
        # Convert URL to HTML using monolith
        subprocess.run(["monolith", url, "-o", html_filename], check=True)

        # Convert HTML to Markdown using pandoc
        subprocess.run(["pandoc", html_filename, "-o", markdown_filename], check=True)

        return {"markdown_file": markdown_filename, "html_file": html_filename}

    except subprocess.CalledProcessError as e:
        raise HTTPException(status_code=500, detail=str(e))
