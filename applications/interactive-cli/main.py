import argparse
import asyncio

import carnivore
from carnivore import util


async def main():
    # Set up argument parsing
    parser = argparse.ArgumentParser(description="Interactive CLI")
    parser.add_argument(
        "--post-process-command", required=True, type=str, help="Post process command"
    )
    args = parser.parse_args()

    while True:
        url = input("Enter a URL: ")
        url = url.strip()
        print("Processing URL...")
        try:
            c = carnivore.Carnivore()
            carnivore_output = await c.archive(url)
            output = await util.post_process(
                carnivore_output, args.post_process_command
            )
        except Exception as e:
            print(f"Failed to process URL: {str(e)}")
            continue
        print(output)


if __name__ == "__main__":
    asyncio.run(main())
