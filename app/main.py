from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel
import subprocess
import os
import uuid

app = FastAPI()


class ClipRequest(BaseModel):
    url: str


@app.post("/clip")
async def clip_url_to_markdown(request: ClipRequest):
    url = request.url
    if not url:
        raise HTTPException(status_code=400, detail="URL is required")

    # Generate unique filenames
    html_filename = f"{uuid.uuid4()}.html"
    markdown_filename = f"{uuid.uuid4()}.md"

    try:
        # Convert URL to HTML using monolith
        subprocess.run(["monolith", url, "-o", html_filename], check=True)

        # Convert HTML to Markdown using pandoc
        subprocess.run(["pandoc", html_filename, "-o", markdown_filename], check=True)

        # Clean up the HTML file
        os.remove(html_filename)

        return {"markdown_file": markdown_filename}

    except subprocess.CalledProcessError as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="debug")
