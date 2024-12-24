import logging
import re
import argparse
import carnivore
from carnivore import util
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
            messages = []
            response = [None]

            async def append_text(message: str, messages=messages, response=response):
                messages.append(message)
                final_message = "\n".join(messages)
                if not response[0]:
                    response[0] = await update.message.reply_text(final_message)
                else:
                    await response[0].edit_text(final_message)

            await append_text(f"Processing URL: {url}")
            try:
                # Call Carnivore
                c = carnivore.Carnivore(args.output_formats, args.output_dir)
                c.set_progress_callback(append_text)
                carnivore_output = await c.archive(url)
                await append_text("Post-processing output")
                output = await util.post_process(
                    carnivore_output, args.post_process_command
                )
            except Exception as e:
                logging.exception(f"Failed to process URL: {url}")
                output = f"Failed to process URL: {url}\nError: {str(e)}"

            messages.append("")
            await append_text(output)
    else:
        await update.message.reply_text("No URL found in the message.")


if __name__ == "__main__":

    def comma_separated_list(value):
        return value.split(",")

    # Set up argument parsing
    parser = argparse.ArgumentParser(description="Telegram Bot")
    parser.add_argument("--token", required=True, help="Telegram bot token")
    parser.add_argument(
        "--channel-id", required=False, type=int, help="Telegram channel ID"
    )
    parser.add_argument(
        "--post-process-command", required=True, type=str, help="Post process command"
    )
    parser.add_argument(
        "--output-formats",
        required=True,
        type=comma_separated_list,
        help="Output formats separated by commas",
    )
    parser.add_argument(
        "--output-dir",
        required=True,
        type=str,
        help="Output directory for the processed files",
    )
    args = parser.parse_args()

    # Use the parsed arguments
    app = ApplicationBuilder().token(args.token).build()
    filter = filters.TEXT & ~filters.COMMAND
    if args.channel_id:
        filter = filter & filters.Chat(chat_id=args.channel_id)
    app.add_handler(MessageHandler(filter, handle_message))
    app.run_polling()
