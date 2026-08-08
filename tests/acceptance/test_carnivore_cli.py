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
