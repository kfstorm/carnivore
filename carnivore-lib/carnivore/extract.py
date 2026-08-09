import json
from pathlib import Path

from .process import invoke_command
from .render import MAX_OUTPUT_BYTES


READABILITY_DIR = Path(__file__).with_name("readability")


async def extract_readability(html: str) -> dict:
    output = await invoke_command(
        ["node", "index.mjs"],
        input=html,
        cwd=READABILITY_DIR,
        max_output_bytes=MAX_OUTPUT_BYTES,
    )
    return json.loads(output)
