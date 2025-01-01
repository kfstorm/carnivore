# Carnivore

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

## Usage

There are multiple ways to use Carnivore. Here are some examples:

### Run Carnivore as an interactive CLI tool

1. Start Carnivore.

    ```sh
    git clone https://github.com/kfstorm/carnivore.git
    cd carnivore
    docker run --rm -it -v ./data:/app/data $(docker build . --quiet)
    ```

2. Paste a URL to the interactive CLI. The bot will process the URL and save the web page in Markdown format in the `data` directory.

### Run Carnivore as a Telegram bot

1. Start Carnivore.

    ```sh
    git clone https://github.com/kfstorm/carnivore.git
    cd carnivore
    args=(
        -e CARNIVORE_APPLICATION=telegram-bot
        -e CARNIVORE_TELEGRAM_TOKEN=...
        -e CARNIVORE_TELEGRAM_CHANNEL_ID=... # optional. If you want to restrict the bot to a specific channel.
    )
    docker run --rm -it "${args[@]}" -v ./data:/app/data $(docker build . --quiet)
    ```

2. Send a URL to the Telegram bot or a channel with the Telegram bot. The bot will process the URL and save the web page in Markdown format in the `data` directory.

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
docker run --rm -it "${args[@]}" $(docker build . --quiet)
```

## Arguments

Common arguments:

- `CARNIVORE_APPLICATION`: Optional. The application to run. Default: `interactive-cli`.
- `CARNIVORE_OUTPUT_DIR`: Optional. The directory to save the generated files. Default: `data`.
- `CARNIVORE_OUTPUT_FORMATS`: Optional. The output formats to generate. Default: `markdown`. Split by `,`.
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

### Carnivore Lib

- **carnivore-lib/**: The main code for web page archiving purposes. It converts web pages to various formats.
- Tools used:
  - [monolith](https://github.com/Y2Z/monolith): Save a web page as a single HTML with all resources embedded. The saved HTML page looks exactly like the online version.
  - [readability](https://github.com/mozilla/readability): Extract the article content from a web page.
  - [pandoc](https://github.com/jgm/pandoc): Convert between various formats, including HTML and Markdown.

### Post-process Scripts

- [post-process/update_files.sh](process/update_files.sh): A script that updates the content of the generated files (mainly used to add frontmatter to the generated Markdown file).
- [post-process/upload_to_github.sh](post-process/upload_to_github.sh): A script that uploads the generated files to a GitHub repository.
