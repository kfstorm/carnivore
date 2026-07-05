# LLM-Friendly Carnivore CLI Plan

## Goal

Build an LLM-friendly Carnivore CLI that uses the official Docker image as the runtime, prints extracted web content to stdout, and can be automatically used by LLM agents through a bundled Skill.

The end-user experience should look like this:

```sh
carnivore-fetch https://example.com
```

The command should run Carnivore inside Docker, use browser-backed rendering and article extraction, and return clean Markdown content suitable for LLM context.

## Non-Goals

- Do not require ordinary users to build the Docker image locally.
- Do not make users install Playwright, Chromium, Pandoc, Node, or monolith on the host.
- Do not replace the existing archiving-oriented workflows.
- Do not make the first version an MCP server.
- Do not require hosted auth, API tokens, or a remote service.

## Confirmed Decisions

- The host wrapper defaults to the official Carnivore Docker image.
- The official Docker image only publishes the `latest` tag for now.
- The first Docker image release should support both `linux/amd64` and `linux/arm64`.
- The first wrapper distribution path is an install script.
- `carnivore-fetch URL` defaults to Markdown output.
- The Skill should also default to raw Markdown output.
- Raw Markdown output should include YAML front matter by default, so URL, title, and other common metadata are available without JSON output.
- `markdown`, `html`, and `full_html` are content formats selected by `--format`.
- `raw` and `json` are CLI output modes selected by `--output`.
- The first version should not implement `--max-chars`; agents can use shell tools to post-process large output when needed.
- The first wrapper should use a named Docker volume for persistent cache by default.
- This document is the handoff artifact for implementation by a later agent.

## High-Level Architecture

```text
Host command: carnivore-fetch
        |
        v
docker run official Carnivore image
        |
        v
entrypoint.sh
        |
        v
applications/fetch/main.py
        |
        v
carnivore.Carnivore.fetch(...)
        |
        v
stdout: raw extracted content or JSON wrapper
stderr: errors by default, progress logs with --verbose
```

The host CLI is a thin wrapper. The real work happens in the Docker container.

## Proposed Files

- `applications/fetch/main.py`
- `skills/carnivore-fetch/bin/carnivore-fetch`
- `scripts/carnivore-fetch`
- `scripts/install-carnivore-fetch.sh`
- `skills/carnivore-fetch/SKILL.md`
- `.github/workflows/docker-image.yml`
- `docs/llm-friendly-cli-plan.md`
- `README.md`
- `entrypoint.sh`
- `carnivore-lib/carnivore/lib.py`
- `carnivore-lib/carnivore/cache.py`
- `carnivore-lib/carnivore/__init__.py`

## Public CLI Contract

Default Markdown output:

```sh
carnivore-fetch https://example.com
```

Structured JSON output mode:

```sh
carnivore-fetch https://example.com --output json
```

Select content format:

```sh
carnivore-fetch https://example.com --format html
carnivore-fetch https://example.com --format full_html
```

Use a custom image:

```sh
CARNIVORE_IMAGE=registry.example.com/carnivore:custom carnivore-fetch https://example.com
```

Use a local development image:

```sh
CARNIVORE_IMAGE=carnivore:local carnivore-fetch https://example.com
```

## Output Rules

- stdout must contain only the requested content.
- stderr should contain errors by default and progress logs only when `--verbose` is used.
- `--format` controls extracted content format: `markdown`, `html`, or `full_html`.
- `--output` controls CLI output mode: `raw` or `json`.
- `--output raw` should print extracted content directly to stdout.
- `--output json` should print a single JSON object to stdout.
- The default should be `--format markdown --output raw`.
- When the default raw Markdown output is used, prepend YAML front matter containing common metadata.
- Failed fetches should print diagnostics to stderr and exit non-zero.
- Progress callback output must go to stderr, not stdout, and only when verbose logging is enabled.
- JSON output should remain available for callers that need a structured envelope rather than Markdown front matter.

## Markdown Front Matter

Raw Markdown output should include YAML front matter by default. This keeps the default agent and human workflow simple while still exposing URL and article metadata without requiring `--output json`.

Important current behavior: the existing archive/post-process path supports front matter, but it does not add it by default. `post-process/update_files.sh` calls `post-process/atomic/add_frontmatter.sh`, and `add_frontmatter.sh` only runs `frontmatter.py` when `CARNIVORE_MARKDOWN_FRONTMATTER_KEY_MAPPING` or `CARNIVORE_MARKDOWN_FRONTMATTER_ADDITIONAL_ARGS` is set. The new fetch CLI should explicitly implement default front matter for raw Markdown output instead of assuming the current archive default already does it.

Implementation options:

- Reuse `post-process/atomic/frontmatter.py` or extract its YAML serialization logic into a reusable Python helper.
- If reusing `frontmatter.py`, call it with no key mapping so it includes all metadata by default, or provide an explicit default mapping for stable keys.
- Keep the existing archive/post-process behavior unchanged unless intentionally broadening that workflow too.

Example default output:

```md
---
url: https://example.com
title: Example title
byline: Author name
excerpt: Short excerpt
siteName: Example
---

# Example title

Markdown content...
```

Front matter requirements:

- Include `url` and `title` when available.
- Include `byline`, `excerpt`, and `siteName` when available.
- Omit missing metadata keys instead of emitting empty strings.
- Escape or serialize values using a real YAML/front matter writer or a safe structured serialization path, not ad hoc string concatenation.
- Apply front matter only to raw Markdown output by default.
- Do not prepend YAML front matter to raw HTML or full HTML output.
- Do not prepend YAML front matter when `--output json` is used.
- `--output json` should keep metadata as JSON fields and content as a separate string.
- The JSON `content` field should contain the extracted content without generated front matter.

## JSON Output Shape

```json
{
  "url": "https://example.com",
  "title": "Example title",
  "byline": "Author name",
  "excerpt": "Short excerpt",
  "siteName": "Example",
  "format": "markdown",
  "output": "json",
  "content": "..."
}
```

Metadata keys should come from Readability metadata when available. Missing metadata fields may be omitted or set to null.

## Library API

Add a public non-archival API to `carnivore.Carnivore`:

```python
async def fetch(self, url: str, format: str = "markdown") -> dict:
    ...
```

The method should:

- Render the URL using existing browser rendering.
- Extract metadata using existing Readability flow.
- Convert to the requested format.
- Return metadata and content.
- Avoid writing output files.
- Reuse existing in-memory cache within the same `Carnivore` instance.
- Use persistent disk cache when `CARNIVORE_CACHE_DIR` is set.
- Validate `format` against `SUPPORTED_FORMATS`.
- Treat `pdf` as unsupported for stdout in the first version unless an explicit output path is provided later.

## Persistent Cache

Persistent cache is important for LLM workflows. An agent may fetch a page, inspect it with one shell command, fail to find the needed text, and then rerun another command against the same URL. Without persistent cache, the Dockerized browser render and conversion pipeline runs again and is slow.

The current `cached()` decorator only uses `Carnivore.cache_store`, which is an in-memory dictionary scoped to one Python process. That cache disappears when the Docker container exits. Mounting a Docker volume is not sufficient by itself; Carnivore must also store cache entries on disk.

Use a named Docker volume by default:

```text
carnivore-cache:/cache
```

The wrapper should pass:

```sh
-v carnivore-cache:/cache
-e CARNIVORE_CACHE_DIR=/cache
```

Prefer a named volume over an anonymous volume. Anonymous volumes are not convenient for repeated CLI calls because users and scripts cannot easily refer to the same volume on the next run. A named volume gives repeatable cache reuse without exposing host filesystem paths.

Do not mount a host cache directory by default. Host cache directories can be added later as an opt-in for users who want inspectable files or custom cleanup policies.

Cache requirements:

- Cache rendered HTML, polished Readability output, embedded HTML, and converted content where practical.
- Include the URL, function name, relevant arguments, and relevant Carnivore version or cache schema version in cache keys.
- Do not cache failed exceptions permanently unless there is a short TTL or explicit negative-cache policy.
- Store cache files under `CARNIVORE_CACHE_DIR` when set.
- Continue to support in-memory cache within a single process.
- Default to persistent cache and add a simple opt-out such as `CARNIVORE_CACHE=0` or `--no-cache` if implementation cost is low.
- Avoid writing final stdout output to the cache as the only cache layer; cache intermediate expensive steps so `raw` and `json` output modes can share work.

Preferred return shape:

```python
{
    "metadata": {
        "url": url,
        "title": "...",
        "byline": "...",
        "excerpt": "...",
        "siteName": "...",
    },
    "format": "markdown",
    "content": "...",
}
```

## Fetch Application

Add `applications/fetch/main.py`.

Responsibilities:

- Parse URL and CLI options.
- Create a `Carnivore` instance.
- Keep logs quiet by default.
- Set progress callback to print to stderr only when `--verbose` is used.
- Call `Carnivore.fetch(...)`.
- Print Markdown directly for default output.
- Print extracted content directly for `--output raw`.
- Print structured JSON for `--output json`.
- Exit with status code 1 on errors.
- Keep compatibility with arguments injected by `entrypoint.sh`.

Suggested arguments:

```text
url
--format markdown|html|full_html
--output raw|json
--verbose
-h|--help
--post-process-command ignored for compatibility
```

`--format` should default to `markdown`.

`--output` should default to `raw`.

Do not implement a first-version `--max-chars` option. If an agent needs a smaller result, the Skill can instruct it to pipe the output through standard shell tools such as `head`, `tail`, `grep`, `rg`, or `wc`, depending on the task.

`--output-formats` and `--output-dir` may still be passed by `entrypoint.sh`; the fetch application can accept them through `Carnivore.setup_arg_parser(parser)` or define compatible arguments explicitly.

## Entrypoint Change

Current `entrypoint.sh` chooses the application but does not forward Docker command arguments.

Change the final line from:

```sh
python "${application_script}" "${args[@]}"
```

to:

```sh
python "${application_script}" "${args[@]}" "$@"
```

This allows commands like:

```sh
docker run --rm -e CARNIVORE_APPLICATION=fetch ghcr.io/kfstorm/carnivore:latest https://example.com
```

## Host Wrapper

Add the canonical host wrapper at `skills/carnivore-fetch/bin/carnivore-fetch`.

Also add `scripts/carnivore-fetch` as a developer convenience entrypoint. It may be a symlink to `../skills/carnivore-fetch/bin/carnivore-fetch` if the repository and target platforms handle symlinks correctly. The canonical file should remain inside the Skill directory so the Skill can ship with the executable helper.

Do not rely on a symlink as the only copy inside the Skill directory. Skill installers, GitHub raw downloads, snapshots, or Windows users may not preserve symlink behavior consistently. The safest layout is a real script file under `skills/carnivore-fetch/bin/` and an optional symlink or tiny delegating script under `scripts/`.

Responsibilities:

- Require Docker.
- Use the official Carnivore Docker image by default.
- Allow override via `CARNIVORE_IMAGE`.
- Pass through `CARNIVORE_ZENROWS_API_KEY`, `CARNIVORE_ZENROWS_PREMIUM_PROXIES`, `CARNIVORE_ZENROWS_JS_RENDERING`, `CARNIVORE_OXYLABS_USER`, and `CARNIVORE_OXYLABS_JS_RENDERING` if set.
- Set `CARNIVORE_APPLICATION=fetch`.
- Set `CARNIVORE_OUTPUT_FORMATS=markdown` by default.
- Set `CARNIVORE_OUTPUT_DIR=/tmp/carnivore`.
- Print wrapper help locally for `--help` and `-h` without requiring Docker.
- Mount named Docker volume `carnivore-cache:/cache` by default.
- Set `CARNIVORE_CACHE_DIR=/cache` by default.
- Pass all user arguments to Docker unchanged.
- Preserve stdout and stderr behavior.
- Avoid building images automatically.
- Do not mount a host cache directory by default.

Optional environment variables and default behavior:

```text
CARNIVORE_IMAGE: official Carnivore image
CARNIVORE_DOCKER_ARGS: none
CARNIVORE_PULL: do not pull before running
CARNIVORE_CACHE_VOLUME: carnivore-cache
CARNIVORE_CACHE: enabled unless set to 0
CARNIVORE_ZENROWS_API_KEY: unset
CARNIVORE_ZENROWS_PREMIUM_PROXIES: unset
CARNIVORE_ZENROWS_JS_RENDERING: unset
CARNIVORE_OXYLABS_USER: unset
CARNIVORE_OXYLABS_JS_RENDERING: unset
```

If `CARNIVORE_PULL=1`, the wrapper may run `docker pull "$CARNIVORE_IMAGE"` before execution.

`CARNIVORE_CACHE_VOLUME` should default to `carnivore-cache`. If `CARNIVORE_CACHE=0`, the wrapper should skip the cache volume mount and set `CARNIVORE_CACHE=0` in the container.

## Install Script

Add `scripts/install-carnivore-fetch.sh` as the first distribution path for the host wrapper.

Responsibilities:

- Install `skills/carnivore-fetch/bin/carnivore-fetch` to a directory on `PATH`.
- Default install target should be `${HOME}/.local/bin/carnivore-fetch`.
- Create the target directory if needed.
- Refuse to overwrite an existing file unless `--force` is passed.
- Print the installed path and a short verification command.
- Do not install Docker or build the image.

Suggested install command for README:

```sh
curl -fsSL https://raw.githubusercontent.com/kfstorm/carnivore/main/scripts/install-carnivore-fetch.sh | sh
```

The install script should install the wrapper only. The wrapper runs the official Carnivore Docker image at execution time.

When installing from GitHub, fetch the canonical wrapper from:

```text
https://raw.githubusercontent.com/kfstorm/carnivore/main/skills/carnivore-fetch/bin/carnivore-fetch
```

## Docker Image Publishing

Add GitHub Actions workflow at `.github/workflows/docker-image.yml`.

Use GitHub Container Registry:

```text
ghcr.io/kfstorm/carnivore
```

Only publish one tag:

```text
latest
```

Build triggers:

```text
push to main
manual workflow_dispatch
```

Recommended first version behavior:

- Publish `:latest` on main branch pushes.
- Publish `:latest` on manual workflow runs.
- Do not publish `:main`, release, or `:sha-*` tags in the first version.
- Keep the registry simple while the project is still early-stage.

Multi-arch target:

```text
linux/amd64
linux/arm64
```

The first public image should support both targets. If one architecture fails in CI, treat that as a release blocker or document the explicit downgrade before publishing.

## Skill

Add Skill at:

```text
skills/carnivore-fetch/SKILL.md
```

Skill frontmatter:

```yaml
---
name: carnivore-fetch
description: Use when reading, summarizing, extracting, or archiving web pages with Carnivore, especially JavaScript-heavy articles, WeChat pages, paywalled pages, bot-protected pages, or pages where built-in WebFetch fails or returns incomplete content.
---
```

Skill body should instruct agents to:

- Use `bin/carnivore-fetch "$URL"` for default LLM-friendly Markdown extraction from inside the Skill.
- Rely on the default Markdown front matter for URL, title, byline, excerpt, site name, and other common metadata.
- Use `bin/carnivore-fetch "$URL" --output json` only when a structured JSON envelope is specifically useful.
- Use Carnivore when browser rendering is needed.
- Use Carnivore when built-in WebFetch fails or returns incomplete content.
- Prefer raw Markdown for ordinary reading, summarization, and extraction tasks.
- Treat stdout as the extracted content. Use `--verbose` only when progress logs are specifically needed.
- Use `bin/carnivore-fetch --help` to check supported options before using non-default arguments.
- For very large output, use ordinary shell tools such as `head`, `tail`, `grep`, `rg`, or `wc` to inspect or narrow the result instead of relying on a Carnivore truncation option.
- Avoid using Carnivore for arbitrary binary downloads.
- If Docker is missing or the command fails, explain the failure and optionally fall back to built-in WebFetch.

Example Skill instruction:

````md
# Carnivore Fetch

Use the bundled `bin/carnivore-fetch` command to extract readable Markdown from web pages using Carnivore's Dockerized browser rendering pipeline.

Run:

```sh
bin/carnivore-fetch "$URL"
```

Use this when a task involves reading, summarizing, extracting, or archiving web pages, especially when pages are JavaScript-heavy, bot-protected, paywalled, or poorly handled by built-in WebFetch.

The default command prints Markdown with YAML front matter to stdout. It is quiet unless an error occurs.

The front matter contains common metadata such as URL, title, byline, excerpt, and site name when available.

When a structured JSON envelope is specifically useful, run:

```sh
bin/carnivore-fetch "$URL" --output json
```

Use `--verbose` only when progress logs are specifically needed.

Use `bin/carnivore-fetch --help` to check supported options before using non-default arguments.

For very large pages, use shell tools such as `head`, `tail`, `grep`, `rg`, or `wc` to inspect or narrow output before using it.

If the command fails because Docker is unavailable, report that Carnivore requires Docker and fall back to another available web-reading tool if appropriate.
````

## skills.sh Publishing

The Skill should live in the public `kfstorm/carnivore` GitHub repository.

Expected install command:

```sh
npx skills add kfstorm/carnivore
```

If the CLI supports installing a single skill by slug, also document:

```sh
npx skills add kfstorm/carnivore/carnivore-fetch
```

Expected skills.sh page:

```text
https://skills.sh/kfstorm/carnivore/carnivore-fetch
```

Publishing steps:

- Merge the Skill into the public repository.
- Verify `npx skills add kfstorm/carnivore`.
- Add a skills.sh badge to README.
- Wait for skills.sh indexing and audit.

README badge:

```md
[![skills.sh](https://skills.sh/b/kfstorm/carnivore)](https://skills.sh/kfstorm/carnivore)
```

## README Updates

Add a section named `LLM-friendly CLI`.

Include:

- What problem it solves.
- Why it uses Docker.
- How to install or run the wrapper.
- How to install the wrapper through the install script.
- How the official image is pulled.
- How stdout and stderr are used, including `--verbose` for progress logs.
- How to use JSON output mode when metadata is needed.
- How the default named Docker volume cache works.
- How to disable cache with `CARNIVORE_CACHE=0`.
- How to install the Skill.
- How to override the Docker image.
- How to use Zenrows or OxyLabs environment variables.

Suggested README example:

````md
## LLM-friendly CLI

Carnivore can be used as a browser-backed web fetcher for LLM agents. It renders pages in Chromium, extracts article content with Readability, converts it to Markdown, and prints the result to stdout.

```sh
carnivore-fetch https://example.com
```

Use JSON output when a structured envelope is useful:

```sh
carnivore-fetch https://example.com --output json
```

Install the wrapper:

```sh
curl -fsSL https://raw.githubusercontent.com/kfstorm/carnivore/main/scripts/install-carnivore-fetch.sh | sh
```

The host command runs the official Docker image. This keeps heavy dependencies such as Chromium, Playwright, Pandoc, Node, and monolith inside the container.

The wrapper enables cache by default with a named Docker volume named `carnivore-cache` so repeated fetches of the same URL can reuse expensive browser rendering and conversion results.

Print progress logs to stderr with `--verbose`:

```sh
carnivore-fetch https://example.com --verbose
```

Show supported options without starting Docker:

```sh
carnivore-fetch --help
```

Disable cache when needed:

```sh
CARNIVORE_CACHE=0 carnivore-fetch https://example.com
```

Install the Skill for compatible agents:

```sh
npx skills add kfstorm/carnivore
```
````

## Testing Plan

Run existing tests:

```sh
./scripts/run-tests.sh
```

Test Docker build locally:

```sh
docker build -t carnivore:local .
```

Test fetch application directly inside Docker:

```sh
docker run --rm \
  -e CARNIVORE_APPLICATION=fetch \
  carnivore:local \
  https://example.com
```

Test wrapper with local image:

```sh
CARNIVORE_IMAGE=carnivore:local skills/carnivore-fetch/bin/carnivore-fetch https://example.com
```

Test persistent cache reuse with the default named volume:

```sh
CARNIVORE_IMAGE=carnivore:local skills/carnivore-fetch/bin/carnivore-fetch https://example.com
CARNIVORE_IMAGE=carnivore:local skills/carnivore-fetch/bin/carnivore-fetch https://example.com
```

The second run should reuse cached expensive intermediate results from the `carnivore-cache` Docker volume.

Verify stdout contains only Markdown by default, or JSON when `--output json` is used.

Verify stderr is quiet by default and contains progress messages with `--verbose`.

Verify failure behavior:

```sh
CARNIVORE_IMAGE=carnivore:local skills/carnivore-fetch/bin/carnivore-fetch not-a-url
```

Verify Skill install:

```sh
npx skills add kfstorm/carnivore
```

## Compatibility Notes

- Docker is required for the host wrapper.
- The default official image should be public.
- The first run may be slow because Docker needs to pull the image.
- Repeated fetches should be faster after the named Docker volume cache is warm.
- Browser rendering can be slow for complex pages.
- Large outputs should be narrowed by the calling agent with standard shell tools when needed.
- PDF output is not part of the first LLM-friendly stdout contract.
- The archiving workflow should continue to work as before.

## Implementation Order

- Add `Carnivore.fetch(...)` to `carnivore-lib/carnivore/lib.py`.
- Extend `carnivore-lib/carnivore/cache.py` to support persistent disk cache under `CARNIVORE_CACHE_DIR`.
- Export any needed API from `carnivore-lib/carnivore/__init__.py`.
- Add `applications/fetch/main.py`.
- Update `entrypoint.sh` to pass `"$@"`.
- Add `skills/carnivore-fetch/bin/carnivore-fetch` as the canonical wrapper.
- Add `scripts/carnivore-fetch` as an optional symlink or delegating script.
- Add `scripts/install-carnivore-fetch.sh`.
- Add GitHub Actions Docker publishing workflow.
- Add `skills/carnivore-fetch/SKILL.md`.
- Update README with LLM-friendly CLI, Docker image, and Skill instructions.
- Run tests and local Docker verification.
- Publish the first `ghcr.io/kfstorm/carnivore:latest` image.
- Verify `npx skills add kfstorm/carnivore`.

## Open Questions

- None at this time.
