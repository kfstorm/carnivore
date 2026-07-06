---
name: carnivore-fetch
description: Use when reading, summarizing, extracting, or archiving web pages with Carnivore, especially JavaScript-heavy articles, WeChat pages, paywalled pages, bot-protected pages, or pages where built-in WebFetch fails or returns incomplete content.
---

# Carnivore Fetch

Use the bundled `bin/carnivore-fetch` command to extract readable Markdown from web pages using Carnivore's Dockerized browser rendering pipeline.

Run:

```sh
bin/carnivore-fetch "$URL"
```

Use this when a task involves reading, summarizing, extracting, or archiving web pages, especially when pages are JavaScript-heavy, bot-protected, paywalled, or poorly handled by built-in WebFetch.

The default command prints Markdown with YAML front matter to stdout. It is quiet unless an error occurs.

Carnivore uses `--resource-mode omit` by default, which removes image, media, and embedded resource elements from Markdown or HTML to keep output focused for LLM usage. Use `--resource-mode link` when original resource links are needed, or `--resource-mode embed` only when a task explicitly needs self-contained archive output. PDF generation embeds resources internally so relative resources work from local temporary HTML.

The front matter contains common metadata such as URL, title, byline, excerpt, and site name when available.

The wrapper enables persistent cache by default through the `carnivore-cache` Docker volume. Do not disable it unless the task specifically requires a fresh fetch.

When a structured JSON envelope is specifically useful, run:

```sh
bin/carnivore-fetch "$URL" --output json
```

Prefer raw Markdown for ordinary reading, summarization, and extraction tasks. Treat stdout as extracted content.

Use `--verbose` only when progress logs are specifically needed.

Use `bin/carnivore-fetch --help` to check supported options before using non-default arguments.

For very large pages, use shell tools such as `head`, `tail`, `grep`, `rg`, or `wc` to inspect or narrow output before using it.

Avoid using Carnivore for arbitrary binary downloads.

If the command fails because Docker is unavailable, report that Carnivore requires Docker and fall back to another available web-reading tool if appropriate.
