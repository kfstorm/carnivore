import json
import os
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).parents[2]


def run_carnivore(url, *args):
    return subprocess.run(
        [sys.executable, "-m", "carnivore", url, *args],
        capture_output=True,
        cwd=PROJECT_ROOT,
        env={
            **os.environ,
            "PYTHONPATH": str(PROJECT_ROOT / "carnivore-lib"),
            "CARNIVORE_CACHE": "0",
        },
        text=True,
        check=False,
    )


def test_carnivore_module_fetches_default_markdown(static_article_url):
    result = run_carnivore(static_article_url)

    assert result.returncode == 0
    assert result.stderr == ""
    assert result.stdout.startswith("---\n")
    assert "title: Static fixture article" in result.stdout
    assert "Static fixture article" in result.stdout


def test_carnivore_module_returns_stable_json(static_article_url):
    result = run_carnivore(static_article_url, "--output", "json")

    assert result.returncode == 0
    assert result.stderr == ""
    output = json.loads(result.stdout)
    assert output["ok"] is True
    assert output["format"] == "markdown"
    assert output["metadata"]["title"] == "Static fixture article"
    assert "This deterministic local article" in output["content"]


def test_carnivore_module_reports_json_errors_without_diagnostics(static_article_url):
    result = run_carnivore(
        static_article_url,
        "--format",
        "pdf",
        "--output",
        "json",
    )

    assert result.returncode == 2
    assert result.stderr == ""
    assert json.loads(result.stdout) == {
        "ok": False,
        "error": {"code": "invalid_input", "detail": "Unsupported format"},
    }


def test_carnivore_module_reports_raw_errors_on_stderr(static_article_url):
    result = run_carnivore(static_article_url, "--resource-mode", "bad")

    assert result.returncode == 2
    assert result.stdout == ""
    assert result.stderr == "invalid_input: Unsupported resource mode\n"
    assert static_article_url not in result.stderr
