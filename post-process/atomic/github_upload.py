# This script uploads a file to a GitHub repository.
# If the file already exists, it will be updated.
#
# Arguments:
# --file-path (required): The path to the file to upload
# --repo (required): The repository to upload the file to. Format: owner/repo
# --repo-path (required): The path in the repository
# --branch (optional): The branch to upload the file to.
#     Default: the repository’s default branch
#
# Environment variables:
# GITHUB_TOKEN: A GitHub token with repo access
#
# Output:
# The HTML URL of the uploaded file

import os
import base64
import requests
import argparse

if __name__ == "__main__":
    github_token = os.getenv("GITHUB_TOKEN")
    if not github_token:
        raise ValueError("GitHub token not provided")

    parser = argparse.ArgumentParser(description="Upload a file to a GitHub repository")
    parser.add_argument(
        "--file-path",
        type=str,
        required=True,
        help="The path to the file to upload",
    )
    parser.add_argument(
        "--repo",
        type=str,
        required=True,
        help="The repository to upload the file to. Format: owner/repo",
    )
    parser.add_argument(
        "--repo-path",
        type=str,
        required=True,
        help="The path in the repository",
    )
    parser.add_argument(
        "--branch",
        type=str,
        default=None,
        help=(
            "The branch to upload the file to."
            " Default: the repository's default branch"
        ),
    )

    args = parser.parse_args()

    common_headers = {
        "Authorization": f"Bearer {github_token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    github_upload_url = f"https://api.github.com/repos/{args.repo}/contents/{requests.utils.quote(args.repo_path)}"  # noqa: B950

    # Check if the file exists
    response = requests.get(
        github_upload_url, headers=common_headers, params={"ref": args.branch}
    )
    if response.status_code == 404:
        sha = None
    else:
        if response.status_code == 200:
            sha = response.json()["sha"]
        else:
            response.raise_for_status()

    # Upload the file
    base64_content = base64.b64encode(open(args.file_path, "rb").read()).decode("utf-8")
    body = {
        "message": f"Upload {os.path.basename(args.file_path)}",
        "content": base64_content,
    }
    if args.branch:
        body["branch"] = args.branch
    if sha:
        body["sha"] = sha
    response = requests.put(github_upload_url, headers=common_headers, json=body)
    response.raise_for_status()
    print(response.json()["content"]["html_url"])
