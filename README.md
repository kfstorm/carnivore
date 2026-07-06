# Carnivore

[![skills.sh](https://skills.sh/b/kfstorm/carnivore)](https://skills.sh/kfstorm/carnivore)

**NOTE: This project is still in early development. Contributions to this project are greatly welcome.**

Carnivore is a simple tool that listens to your web page article archiving needs, removes clutter in the web pages, converts to various file formats, and does whatever you like to deal with converted files. You can combine this tool with your favorite document reader to read, comment, and modify articles.

**Owning your data is important. Saving your data with open formats is also important.**

## Features

Main process:

1. Trigger web page archiving by various methods.
    - Paste a URL to the interactive CLI.
    - Send a URL to a Telegram bot or a Telegram channel with a Telegram bot involved.
    - (More triggering methods could be added as needed.)
2. Archive the web page with various formats.
    - A single HTML file with all CSS/JavaScript/image/... resources included. Looks exactly like the original web page.
    - A polished version of the above HTML file that removes clutter and only keeps the article content.
    - A Markdown version of the polished web page.
    - A PDF document of the original web page.
    - (More formats like whole page image could be added as needed.)
3. Process the generated files the way you like.
    - Upload files to a GitHub repo.
    - Call a customized post-processing script written by yourself.
    - (More post-processing methods could be added as needed.)

Other features:

- Bypass bot detection by using services provided by Zenrows or OxyLabs.
- Bypass paywalls with the help of chrome extension Bypass Paywalls Clean.

Supported output formats:

- `markdown`: The article content in Markdown format.
- `html`: The article content in HTML format.
- `full_html`: The full web page in HTML format.
- `pdf`: The full web page in PDF format.

Output formats could be customized by setting the `CARNIVORE_OUTPUT_FORMATS` environment variable. e.g. `markdown,html,full_html` (split by `,`). Default: `markdown`.

## LLM-friendly CLI

Carnivore can be used as a browser-backed web fetcher for LLM agents. It renders pages in Chromium, extracts article content with Readability, converts it to Markdown, and prints the result to stdout.

```sh
carnivore-fetch https://example.com
```

The default output is raw Markdown with YAML front matter containing available metadata such as URL, title, byline, excerpt, and site name. The CLI is quiet unless an error occurs.

Use JSON output when a structured envelope is useful:

```sh
carnivore-fetch https://example.com --output json
```

Select an extracted content format with `--format`:

```sh
carnivore-fetch https://example.com --format html
carnivore-fetch https://example.com --format full_html
```

Print progress logs to stderr with `--verbose`:

```sh
carnivore-fetch https://example.com --verbose
```

Show supported options without starting Docker:

```sh
carnivore-fetch --help
```

Install the host wrapper:

```sh
curl -fsSL https://raw.githubusercontent.com/kfstorm/carnivore/main/scripts/install-carnivore-fetch.sh | sh
```

The wrapper runs the official Docker image at execution time. This keeps heavy dependencies such as Chromium, Playwright, Pandoc, Node, and monolith inside the container. Docker is required on the host, but ordinary users do not need to clone the repository or build the image locally.

You can also run the fetch application directly with Docker:

```sh
docker run --rm -e CARNIVORE_APPLICATION=fetch ghcr.io/kfstorm/carnivore:latest https://example.com
```

The first run may be slow because Docker needs to pull the image.

The wrapper enables cache by default with a named Docker volume named `carnivore-cache` so repeated fetches of the same URL can reuse expensive browser rendering and conversion results.

Carnivore does not embed external resources in Markdown or HTML outputs by default. This keeps output smaller for scripts and LLM agents. Set `--embed-resources` or `CARNIVORE_EMBED_RESOURCES=true` when using Carnivore for webpage archiving and you need self-contained Markdown or HTML output. PDF generation always embeds resources internally so relative images and styles still work from the temporary local HTML file.

Disable cache when needed:

```sh
CARNIVORE_CACHE=0 carnivore-fetch https://example.com
```

Override the Docker image for local development or private registries:

```sh
CARNIVORE_IMAGE=carnivore:local carnivore-fetch https://example.com
```

If configured on the host, the wrapper passes through `CARNIVORE_EMBED_RESOURCES`, `CARNIVORE_ZENROWS_API_KEY`, `CARNIVORE_ZENROWS_PREMIUM_PROXIES`, `CARNIVORE_ZENROWS_JS_RENDERING`, `CARNIVORE_OXYLABS_USER`, and `CARNIVORE_OXYLABS_JS_RENDERING`.

Wrapper options and environment variables:

| Name | Default behavior |
| --- | --- |
| `--format markdown\|html\|full_html` | Uses `markdown`. |
| `--output raw\|json` | Uses `raw`. |
| `--embed-resources` | Does not embed external resources in Markdown or HTML outputs. PDF generation embeds internally. |
| `--verbose` | Stays quiet unless an error occurs. |
| `-h`, `--help` | Does not show help unless requested. |
| `CARNIVORE_CACHE` | Enables cache. Set `CARNIVORE_CACHE=0` to disable it. |
| `CARNIVORE_CACHE_VOLUME` | Uses the `carnivore-cache` Docker volume. |
| `CARNIVORE_IMAGE` | Uses the official Carnivore image. Set it to override the image. |
| `CARNIVORE_PULL` | Does not pull before running. Set `CARNIVORE_PULL=1` to pull first. |
| `CARNIVORE_DOCKER_ARGS` | Passes no extra Docker arguments. |
| `CARNIVORE_EMBED_RESOURCES` | Does not embed external resources in Markdown or HTML outputs. Set `CARNIVORE_EMBED_RESOURCES=true` for self-contained archive output. PDF generation embeds internally. |
| `CARNIVORE_ZENROWS_API_KEY` | Not passed unless set on the host. |
| `CARNIVORE_ZENROWS_PREMIUM_PROXIES` | Not passed unless set on the host. |
| `CARNIVORE_ZENROWS_JS_RENDERING` | Not passed unless set on the host. |
| `CARNIVORE_OXYLABS_USER` | Not passed unless set on the host. |
| `CARNIVORE_OXYLABS_JS_RENDERING` | Not passed unless set on the host. |

Install the Skill for compatible agents:

```sh
npx skills add kfstorm/carnivore --skill carnivore-fetch
```

Add `--global` to install the Skill globally for supported agents.

## Usage

There are multiple ways to use Carnivore. Here are some examples:

### Run Carnivore as an interactive CLI tool

1. Start Carnivore.

    ```sh
    mkdir -p data
    docker run --rm -it -v ./data:/app/data ghcr.io/kfstorm/carnivore:latest
    ```

2. Paste a URL to the interactive CLI. The bot will process the URL and save the web page in Markdown format in the `data` directory.

### Run Carnivore as a Telegram bot

1. Start Carnivore.

    ```sh
    args=(
        -e CARNIVORE_APPLICATION=telegram-bot
        -e CARNIVORE_TELEGRAM_TOKEN=...
        -e CARNIVORE_TELEGRAM_CHANNEL_ID=... # optional. If you want to restrict the bot to a specific channel.
    )
    mkdir -p data
    docker run --rm -it "${args[@]}" -v ./data:/app/data ghcr.io/kfstorm/carnivore:latest
    ```

2. Send a URL to the Telegram bot or a channel with the Telegram bot. The bot will process the URL and save the web page in Markdown format in the `data` directory.

### Run Carnivore as a fetch application

```sh
docker run --rm -e CARNIVORE_APPLICATION=fetch ghcr.io/kfstorm/carnivore:latest https://example.com
```

The fetch application prints extracted content to stdout instead of saving files to the output directory.

## Post-processing Customization

You can customize the post-processing by:

1. Choose a pre-defined post-processing command.
2. Write your post-processing command and mount it into the container.

To configure the post-processing command, set the `CARNIVORE_POST_PROCESS_COMMAND` environment variable. The command should be a shell command.

e.g. To use the pre-defined post-processing command to upload the generated files to a GitHub repository:

```bash
args=(
    -e CARNIVORE_POST_PROCESS_COMMAND=post-process/upload_to_github.sh
    -e CARNIVORE_GITHUB_REPO=username/repo_name
    -e CARNIVORE_GITHUB_BRANCH=master # optional.
    -e CARNIVORE_GITHUB_REPO_DIR=path/in/repo
    -e CARNIVORE_GITHUB_TOKEN=...
    -e CARNIVORE_OUTPUT_FORMATS="markdown,html,full_html,pdf" # optional. upload multiple formats of the web page.
    -e CARNIVORE_MARKDOWN_FRONTMATTER_KEY_MAPPING="url:url,title:title" # optional. you may want to add frontmatter at the beginning of the Markdown file.
    -e CARNIVORE_MARKDOWN_FRONTMATTER_ADDITIONAL_ARGS="--timestamp-key date-created" # optional. you may want to add the timestamp to the frontmatter.
    -e TZ=Asia/Shanghai # optional. you may want to customize the timezone.
)
docker run --rm -it "${args[@]}" ghcr.io/kfstorm/carnivore:latest
```

## Arguments

Common arguments:

- `CARNIVORE_APPLICATION`: Optional. The application to run. Available values include `interactive-cli`, `telegram-bot`, and `fetch`. Default: `interactive-cli`.
- `CARNIVORE_OUTPUT_DIR`: Optional. The directory to save the generated files. Default: `data`.
- `CARNIVORE_OUTPUT_FORMATS`: Optional. The output formats to generate. Default: `markdown`. Split by `,`.
- `CARNIVORE_EMBED_RESOURCES`: Optional. Set to `true` to embed external resources before generating Markdown or HTML outputs. Default: resources are not embedded in Markdown or HTML, which is recommended for fetch/LLM usage. Enable this for self-contained archive output. PDF generation embeds resources internally regardless of this setting.
- `CARNIVORE_POST_PROCESS_COMMAND`: Optional. The post-processing command to run. Default: `post-process/update_files.sh`.
- `CARNIVORE_MARKDOWN_FRONTMATTER_KEY_MAPPING`: Optional. The key mapping for the frontmatter in the Markdown file. The format is `metadata_key1:frontmatter_key1,metadata_key2:frontmatter_key2`. e.g.: `url:url,title:title`.
- `CARNIVORE_MARKDOWN_FRONTMATTER_ADDITIONAL_ARGS`: Optional. Additional arguments for the frontmatter in the Markdown file. e.g. `--timestamp-key date-created --timestamp-format %Y-%m-%d %H:%M:%S`.

Telegram-related arguments (Optional. Only used when the application is `telegram-bot`):

- `CARNIVORE_TELEGRAM_TOKEN`: The Telegram bot token.
- `CARNIVORE_TELEGRAM_CHANNEL_ID`: Optional. The Telegram channel ID to restrict the bot to.

GitHub-related arguments (Optional. Only used when the post-processing command is `post-process/upload_to_github.sh`):

- `CARNIVORE_GITHUB_REPO`: The GitHub repository to upload the generated files.
- `CARNIVORE_GITHUB_BRANCH`: Optional. The branch to upload the generated files. Default: `master`.
- `CARNIVORE_GITHUB_REPO_DIR`: The directory in the GitHub repository to upload the generated files.
- `CARNIVORE_GITHUB_TOKEN`: The GitHub token to upload the generated files.

Zenrows-related arguments (Optional. For bypassing bot detection such as Cloudflare DDOS protection):

- `CARNIVORE_ZENROWS_API_KEY`: The Zenrows API key.
- `CARNIVORE_ZENROWS_PREMIUM_PROXIES`: Optional. Set to `true` to enable premium proxies.
- `CARNIVORE_ZENROWS_JS_RENDERING`: Optional. Set to `true` to enable JS rendering.

OxyLabs-related arguments (Optional. For bypassing bot detection such as Cloudflare DDOS protection):

- `CARNIVORE_OXYLABS_USER`: The OxyLabs username and password in the format `username:password`.
- `CARNIVORE_OXYLABS_JS_RENDERING`: Optional. Set to `true` to enable JS rendering.

## Components

### Applications

- **applications/interactive-cli**: An interactive CLI tool that reads URLs pasted in the terminal, archives webpages using **Carnivore Lib**, and invokes a post-processing command for further processing.

- **applications/telegram-bot**: A Telegram bot that listens for URLs in messages sent to the bot or sent to a channel with the bot, archives webpages using **Carnivore Lib**, and invokes a post-processing command for further processing.

- **applications/fetch**: A non-interactive fetch application that reads a URL from command arguments and prints extracted content to stdout for scripts and LLM agents.

### Carnivore Lib

- **carnivore-lib/**: The main code for web page archiving purposes. It converts web pages to various formats.
- Tools used:
  - [monolith](https://github.com/Y2Z/monolith): Save a web page as a single HTML with all resources embedded. The saved HTML page looks exactly like the online version.
  - [readability](https://github.com/mozilla/readability): Extract the article content from a web page.
  - [pandoc](https://github.com/jgm/pandoc): Convert between various formats, including HTML and Markdown.

### Post-process Scripts

- [post-process/update_files.sh](process/update_files.sh): A script that updates the content of the generated files (mainly used to add frontmatter to the generated Markdown file).
- [post-process/upload_to_github.sh](post-process/upload_to_github.sh): A script that uploads the generated files to a GitHub repository.
