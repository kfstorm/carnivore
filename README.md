# Carnivore

**NOTE: This project is still in early development. Contributions to this project are greatly welcome.**

Carnivore is a simple tool that listens to your web page article archiving needs, removes clutter in the web pages, converts to various file formats, and does whatever you like to deal with converted files. You can combine this tool with your favorite document reader to read, comment, and modify articles.

**Owning your data is important. Saving your data with open formats is also important.**

## Features

1. Trigger web page archiving by:
    - Send a URL to a Telegram channel with a Telegram bot involved.
    - (More triggering methods could be added as needed.)
2. Archive the web page with various formats:
    - A single HTML file with all CSS/JavaScript/image/... resources included. Looks exactly like the original web page. (Thank you, [monolith](https://github.com/Y2Z/monolith)!)
    - A polished version of the above HTML file that removes clutter and only keeps the article content. (Thank you, [readability](https://github.com/mozilla/readability)!)
    - A Markdown version of the polished web page. (Thank you, [pandoc](https://github.com/jgm/pandoc)!)
    - (More formats like PDF and whole page image could be added as needed.)
3. Process the archived files the way you like:
    - Save files to a local path.
    - Upload files to a GitHub repo.
    - (Call a customized post-processing script written by yourself.)
    - (More post-processing methods could be added as needed.)

## Usage

1. Start the service.

    ```sh
    git clone https://github.com/kfstorm/carnivore.git
    cd carnivore
    args=(
        -e TELEGRAM_TOKEN=...
        -e TELEGRAM_CHANNEL_ID=...
    )
    docker run --rm -it "${args[@]}" -v ./data:/app/data $(docker build . --quiet)
    ```

2. Send a URL to the specified Telegram channel. The bot will process the URL and (the post-processing part) save the article content in Markdown format in the `data` directory.

## Post-processing Customization

You can customize the post-processing by:

1. Choose a pre-defined post-processing command.
2. Write your post-processing command and mount it into the container.

To configure the post-processing command, set the `POST_PROCESS_COMMAND` environment variable. The command should be a shell command.

e.g. To use the pre-defined post-processing command to upload the clipped Markdown and HTML files to a GitHub repository:

```bash
args=(
    -e TELEGRAM_TOKEN=...
    -e TELEGRAM_CHANNEL_ID=...
    -e POST_PROCESS_COMMAND=post-process/upload_to_github.sh
    -e GITHUB_REPO=username/repo_name
    -e GITHUB_BRANCH=master # optional.
    -e GITHUB_REPO_DIR=path/in/repo
    -e GITHUB_TOKEN=...
    -e CONTENT_FORMATS="markdown,html,full_html,rendered_html" # optional. upload multiple versions of the web page. Default: markdown.
    -e MARKDOWN_FRONTMATTER_KEY_MAPPING="url:url,title:title" # optional. you may want to add frontmatter at the beginning of the Markdown file.
    -e MARKDOWN_FRONTMATTER_ADDITIONAL_ARGS="--timestamp-key date-created" # optional. you may want to add the timestamp to the frontmatter.
    -e TZ=Asia/Shanghai # optional. you may want to customize the timezone.
)
docker run --rm -it "${args[@]}" $(docker build . --quiet)
```

## Components

### Telegram Bot

- **telegram-bot/app/main.py**: The main script for the Telegram bot. It listens for URLs in messages in a specific channel, archives webpages using **Carnivore Core**, and invokes a post-processing command for further processing.

### Carnivore Core

- **carnivore/app/main.py**: The main script for web page archiving purposes. It converts web pages to various formats, currently HTML and Markdown.
- Tools used:
  - [monolith](https://github.com/Y2Z/monolith): Save a web page as a single HTML with all resources embedded. The saved HTML page looks exactly like the online version.
  - [readability](https://github.com/mozilla/readability): Extract the article content from a web page.
  - [pandoc](https://github.com/jgm/pandoc): Convert between various formats, including HTML and Markdown.

### Post-process Scripts

- [post-process/save_files.sh](process/save_files.sh): A script that saves the processed content to any directory (customizable via the `CARNIVORE_OUTPUT_DIR` environment variable).
- [post-process/upload_to_github.sh](post-process/upload_to_github.sh): A script that uploads the processed content to a GitHub repository.
