# Markclipper

**NOTE: This project is still in early development.**

This project is a Telegram bot that processes URLs sent in a specific channel. The bot converts web pages to Markdown format and saves the content to a specified directory.

## Usage

1. Start the telegram bot.

```sh
git clone https://github.com/kfstorm/markclipper.git
cd markclipper
docker run --rm -it -e TELEGRAM_TOKEN=... -e TELEGRAM_CHANNEL_ID=... $(docker build . --quiet)
```

2. Send a URL in the specified Telegram channel. The bot will process the URL and save the content to the specified directory.

## Components

### Telegram Bot

- **telegram-bot/app/main.py**: The main script for the Telegram bot. It listens for messages in a specific channel, processes URLs using the [markclipper](http://_vscodecontentref_/0) tool, and saves the content to a specified directory.

### Markclipper

- **markclipper/app/main.py**: The main script for the [markclipper](http://_vscodecontentref_/1) tool. It converts web pages to Markdown format.
- Tools used:
  - [monolith](https://github.com/Y2Z/monolith): download web pages as single HTML files.
  - [readability](https://github.com/mozilla/readability): parse HTML content and extract readable content and metadata.
  - [pandoc](https://github.com/jgm/pandoc): convert HTML to Markdown.
