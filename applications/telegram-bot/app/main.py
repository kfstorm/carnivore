import logging
import re
import argparse
import common
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


# Define the message handler
async def handle_message(update: Update, context) -> None:
    text = update.message.text
    urls = url_pattern.findall(text)
    # deduplicate the URLs
    urls = set(urls)
    if urls:
        for url in urls:
            response_message = f"Processing URL: {url}"
            processing_message = await update.message.reply_text(response_message)
            try:
                # Call the carnivore function
                output = common.process(url, args.post_process_command)
            except Exception as e:
                logging.exception(f"Failed to process URL: {url}")
                output = f"Failed to process URL: {url}\nError: {str(e)}"
            # Generate a response message
            final_response = output
            # Edit the initial message with the final response
            await processing_message.edit_text(final_response)
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
        "--post-process-command", required=True, type=str, help="Post process command"
    )
    args = parser.parse_args()

    # Use the parsed arguments
    app = ApplicationBuilder().token(args.token).build()
    app.add_handler(
        MessageHandler(
            filters.Chat(chat_id=args.channel_id) & filters.TEXT & ~filters.COMMAND,
            handle_message,
        )
    )
    app.run_polling()