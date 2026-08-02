import os
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).parents[2]


def run_fetch(url, *args):
    return subprocess.run(
        [
            sys.executable,
            "applications/fetch/main.py",
            url,
            "--output-formats",
            "markdown",
            "--output-dir",
            "data",
            *args,
        ],
        capture_output=True,
        cwd=PROJECT_ROOT,
        env={**os.environ, "CARNIVORE_CACHE": "0"},
        text=True,
        check=False,
    )


def test_fetch_cli_writes_static_article_to_stdout(static_article_url):
    result = run_fetch(static_article_url)

    assert result.returncode == 0
    assert result.stderr == ""
    assert result.stdout.startswith("---\n")
    assert "title: Static fixture article" in result.stdout
    assert "Static fixture article" in result.stdout


def test_fetch_cli_follows_redirects(redirect_article_url):
    result = run_fetch(redirect_article_url)

    assert result.returncode == 0
    assert result.stderr == ""
    assert "Static fixture article" in result.stdout


def test_fetch_cli_includes_early_javascript_content(fixture_server):
    result = run_fetch(f"{fixture_server}/javascript-early")

    assert result.returncode == 0
    assert result.stderr == ""
    assert "Early JavaScript fixture content." in result.stdout


def test_fetch_cli_excludes_late_javascript_content(fixture_server):
    result = run_fetch(f"{fixture_server}/javascript-late")

    assert result.returncode == 0
    assert result.stderr == ""
    assert "Late JavaScript fixture content." not in result.stdout


def test_fetch_cli_handles_delayed_responses(fixture_server):
    result = run_fetch(f"{fixture_server}/delayed")

    assert result.returncode == 0
    assert result.stderr == ""
    assert "Delayed fixture article" in result.stdout


def test_fetch_cli_omits_resources_by_default(fixture_server):
    result = run_fetch(f"{fixture_server}/resources")

    assert result.returncode == 0
    assert result.stderr == ""
    assert "Resource fixture article" in result.stdout
    assert "/pixel.png" not in result.stdout


def test_fetch_cli_keeps_resource_links_when_requested(fixture_server):
    result = run_fetch(f"{fixture_server}/resources", "--resource-mode", "link")

    assert result.returncode == 0
    assert result.stderr == ""
    assert "/pixel.png" in result.stdout


def test_fetch_cli_reports_http_failures_on_stderr(http_error_url):
    result = run_fetch(http_error_url)

    assert result.returncode != 0
    assert result.stdout == ""
    assert "Status code: 500" in result.stderr
