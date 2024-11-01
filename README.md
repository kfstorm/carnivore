# Carnivore

**NOTE: This project is still in early development.**

This project is a Telegram bot that processes URLs sent in a specific channel. The bot converts web pages to Markdown (and HTML) format and do various kinds of post-processing.

**Owning your data is important. Saving your data with open formats is also important.**

## Usage

1. Start the telegram bot.

    ```sh
    git clone https://github.com/kfstorm/carnivore.git
    cd carnivore
    args=(
        -e TELEGRAM_TOKEN=...
        -e TELEGRAM_CHANNEL_ID=...
        # Add more environment variables as needed
    )
    docker run --rm -it "${args[@]}" $(docker build . --quiet)
    ```

2. Send a URL in the specified Telegram channel. The bot will process the URL and send a reply message with the metadata of the article. (This is the default behavior if you don't customize the post-processing.)

## Post-Processing Customization

You can customize the post-processing by:

1. Choose a pre-defined post-processing command.
2. Write your own post-processing command and mount it into the container.

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
    -e CONTENT_FORMATS="markdown,html,full_html" # optional. upload multiple versions of the web page. Default: markdown.
    -e MARKDOWN_FRONTMATTER_KEY_MAPPING="url:url,title:title" # optional. you may want to add frontmatter at the beginning of the Markdown file.
    -e MARKDOWN_FRONTMATTER_ADDITIONAL_ARGS="--timestamp-key date-created" # optional. you may want to add the timestamp to the frontmatter.
    -e TZ=Asia/Shanghai # optional. you may want to customize the timezone.
)
docker run --rm -it "${args[@]}" $(docker build . --quiet)
```

## Components

### Telegram Bot

- **telegram-bot/app/main.py**: The main script for the Telegram bot. It listens for URLs in messages in a specific channel, clip webpages using the **carnivore** tool, and invokes a post-processing command for further processing.

### Carnivore Core

- **carnivore/app/main.py**: The main script of the **carnivore** tool. It converts web pages to various formats, currently HTML and Markdown.

### Post-Process Scripts

- [post-process/print_metadata.sh](process/print_metadata.sh): A script that prints the metadata of the processed content. (The default post-processing command for demonstration purposes.)
- [post-process/upload_to_github.sh](post-process/upload_to_github.sh): A script that uploads the processed content to a GitHub repository.
