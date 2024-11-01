# This script accepts article metadata as a command line arg and generate Markdown frontmatter for the article.

import argparse
import datetime
import json
import sys
from ruamel.yaml import YAML

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Generate Markdown frontmatter for an article"
    )
    parser.add_argument(
        "--metadata",
        type=str,
        required=True,
        help="Article metadata in JSON format",
    )
    parser.add_argument(
        "--key-mapping",
        type=str,
        default=None,
        help="Map metadata keys to frontmatter keys."
        " The format is `metadata_key1:frontmatter_key1,metadata_key2:frontmatter_key2`."
        " Only the keys specified will be included in the frontmatter."
        " If not provided, all metadata keys will be included. If an empty string is provided, no keys will be included.",
    )
    parser.add_argument(
        "--timestamp-key",
        type=str,
        default=None,
        help="Add an additional key to the frontmatter with the current timestamp.",
    )
    parser.add_argument(
        "--timestamp-format",
        type=str,
        default="%Y-%m-%d %H:%M:%S",
        help="The format to use for the timestamp.",
    )
    args = parser.parse_args()

    metadata = json.loads(args.metadata)
    if args.key_mapping is not None:
        key_mapping = dict(
            tuple(mapping.split(":"))
            for mapping in args.key_mapping.split(",")
            if len(mapping) > 0
        )
    else:
        key_mapping = None

    frontmatter_data = {}
    if key_mapping is None:
        for key, value in metadata.items():
            frontmatter_data[key] = value
    else:
        for metadata_key, frontmatter_key in key_mapping.items():
            if metadata_key in metadata:
                frontmatter_data[frontmatter_key] = metadata[metadata_key]

    if args.timestamp_key:
        frontmatter_data[args.timestamp_key] = datetime.datetime.now().strftime(
            args.timestamp_format
        )

    # dump YAML of frontmatter to stdout
    print("---")
    with YAML(output=sys.stdout) as yaml:
        yaml.dump(frontmatter_data)
    print("---")
