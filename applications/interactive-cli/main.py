import argparse
import asyncio

import carnivore
from carnivore import util


def comma_separated_list(value):
    return value.split(",")


async def main():
    # Set up argument parsing
    parser = argparse.ArgumentParser(description="Interactive CLI")
    parser.add_argument(
        "--post-process-command", required=True, type=str, help="Post process command"
    )
    parser.add_argument(
        "--output-formats",
        required=True,
        type=comma_separated_list,
        help="Output formats separated by commas",
    )
    args = parser.parse_args()

    async def append_text(message: str):
        print(message)

    while True:
        url = input("Enter a URL: ")
        url = url.strip()
        print("Processing URL...")
        try:
            c = carnivore.Carnivore(args.output_formats)
            c.set_progress_callback(append_text)
            carnivore_output = await c.archive(url)
            output = await util.post_process(
                carnivore_output, args.post_process_command
            )
        except Exception as e:
            print(f"Failed to process URL: {str(e)}")
            continue
        print()
        print(output)


if __name__ == "__main__":
    asyncio.run(main())
