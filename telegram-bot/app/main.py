import datetime
import logging
import os
import re
import json
import argparse
import shutil
import asyncio
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler
import telegram.ext.filters as filters

# Configure logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Precompile the URL pattern
url_pattern = re.compile(r"https?://\S+")


# Define the markclipper function (assuming it's already implemented)
async def markclipper(url: str, output_dir: str) -> dict:
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
    temp_output_dir = os.path.join(base_dir, "data")
    shutil.rmtree(temp_output_dir, ignore_errors=True)

    process = await asyncio.create_subprocess_exec(
        "python",
        os.path.join(base_dir, "markclipper/app/main.py"),
        "--url",
        url,
        "--output-dir",
        temp_output_dir,
        "--filename-method",
        "title",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await process.communicate()
    if process.returncode != 0:
        raise Exception(f"Subprocess failed with error: {stderr.decode()}")

    output = json.loads(stdout)

    with open(output["metadata_file"], "r") as f:
        metadata = json.load(f)
    with open(output["markdown_file"], "r") as f:
        markdown_content = f.read()
    shutil.rmtree(temp_output_dir, ignore_errors=True)

    if not os.path.exists(output_dir):
        os.makedirs(output_dir, exist_ok=True)
    filename = os.path.split(output["markdown_file"])[1]
    with open(os.path.join(output_dir, filename), "w") as f:
        title = metadata.get("title")
        date_created = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        f.write("---\n")
        f.write(f"title: {title}\n")
        f.write(f"url: {url}\n")
        f.write(f"date-created: {date_created}\n")
        f.write("---\n")
        f.write(markdown_content)

    return {
        "title": title,
    }


# Define the message handler
async def handle_message(update: Update, context) -> None:
    text = update.message.text
    urls = url_pattern.findall(text)
    # deduplicate the URLs
    urls = set(urls)
    if urls:
        for url in urls:
            try:
                await update.message.reply_text(f"Processing URL: {url}")
                # Call the markclipper function
                metadata = await markclipper(url, output_dir)
                title = metadata["title"]
                # Generate a response message
                response_message = f"Processed URL: {url}\nTitle: {title}"
                # Send the result back to the same chat
                await update.message.reply_text(response_message)
            except Exception as e:
                await update.message.reply_text(
                    f"Failed to process URL: {url}\nError: {str(e)}"
                )
    else:
        await update.message.reply_text("No URL found in the message.")


if __name__ == "__main__":
    # Set up argument parsing
    parser = argparse.ArgumentParser(description="Telegram Bot")
    parser.add_argument("--token", required=True, help="Telegram bot token")
    parser.add_argument(
        "--channel-id", required=True, type=int, help="Telegram channel ID"
    )
    parser.add_argument(
        "--output-dir", required=True, help="Output directory for the markdown files"
    )
    args = parser.parse_args()
    output_dir = args.output_dir

    # Use the parsed arguments
    app = ApplicationBuilder().token(args.token).build()
    app.add_handler(
        MessageHandler(
            filters.Chat(chat_id=args.channel_id) & filters.TEXT & ~filters.COMMAND,
            handle_message,
        )
    )
    app.run_polling()
