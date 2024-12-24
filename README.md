# Carnivore

**NOTE: This project is still in early development. Contributions to this project are greatly welcome.**

Carnivore is a simple tool that listens to your web page article archiving needs, removes clutter in the web pages, converts to various file formats, and does whatever you like to deal with converted files. You can combine this tool with your favorite document reader to read, comment, and modify articles.

**Owning your data is important. Saving your data with open formats is also important.**

## Features

1. Trigger web page archiving by various methods.
    - Paste a URL to the interactive CLI.
    - Send a URL to a Telegram bot or a Telegram channel with a Telegram bot involved.
    - (More triggering methods could be added as needed.)
2. Archive the web page with various formats.
    - A single HTML file with all CSS/JavaScript/image/... resources included. Looks exactly like the original web page. (Thank you, [monolith](https://github.com/Y2Z/monolith)!)
    - A polished version of the above HTML file that removes clutter and only keeps the article content. (Thank you, [readability](https://github.com/mozilla/readability)!)
    - A Markdown version of the polished web page. (Thank you, [pandoc](https://github.com/jgm/pandoc)!)
    - (More formats like PDF and whole page image could be added as needed.)
3. Process the archived files the way you like.
    - Save files to a local path.
    - Upload files to a GitHub repo.
    - Call a customized post-processing script written by yourself.
    - (More post-processing methods could be added as needed.)

Supported output formats:

- `markdown`: The article content in Markdown format.
- `html`: The article content in HTML format.
- `full_html`: The full web page in HTML format.

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

2. Paste a URL to the interactive CLI. The bot will process the URL and save the article content in Markdown format in the `data` directory.

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

2. Send a URL to the Telegram bot or a channel with the Telegram bot. The bot will process the URL and save the article content in Markdown format in the `data` directory.

## Post-processing Customization

You can customize the post-processing by:

1. Choose a pre-defined post-processing command.
2. Write your post-processing command and mount it into the container.

To configure the post-processing command, set the `CARNIVORE_POST_PROCESS_COMMAND` environment variable. The command should be a shell command.

e.g. To use the pre-defined post-processing command to upload the clipped Markdown and HTML files to a GitHub repository:

```bash
args=(
    -e CARNIVORE_POST_PROCESS_COMMAND=post-process/upload_to_github.sh
    -e CARNIVORE_GITHUB_REPO=username/repo_name
    -e CARNIVORE_GITHUB_BRANCH=master # optional.
    -e CARNIVORE_GITHUB_REPO_DIR=path/in/repo
    -e CARNIVORE_GITHUB_TOKEN=...
    -e CARNIVORE_OUTPUT_FORMATS="markdown,html,full_html" # optional. upload multiple formats of the web page.
    -e CARNIVORE_MARKDOWN_FRONTMATTER_KEY_MAPPING="url:url,title:title" # optional. you may want to add frontmatter at the beginning of the Markdown file.
    -e CARNIVORE_MARKDOWN_FRONTMATTER_ADDITIONAL_ARGS="--timestamp-key date-created" # optional. you may want to add the timestamp to the frontmatter.
    -e TZ=Asia/Shanghai # optional. you may want to customize the timezone.
)
docker run --rm -it "${args[@]}" $(docker build . --quiet)
```

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

- [post-process/save_files.sh](process/save_files.sh): A script that saves the processed content to any directory (customizable via the `CARNIVORE_OUTPUT_DIR` environment variable).
- [post-process/upload_to_github.sh](post-process/upload_to_github.sh): A script that uploads the processed content to a GitHub repository.
