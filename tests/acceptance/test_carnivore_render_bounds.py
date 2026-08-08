import os
import subprocess
import sys
import time
from pathlib import Path


PROJECT_ROOT = Path(__file__).parents[2]


def run_carnivore(url, *args, timeout=60):
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
        timeout=timeout,
    )


def test_carnivore_rejects_non_http_and_non_absolute_input():
    result = run_carnivore("file:///etc/hostname")

    assert result.returncode == 2
    assert result.stdout == ""
    assert "invalid_input" in result.stderr


def test_carnivore_follows_a_single_redirect(redirect_article_url):
    result = run_carnivore(redirect_article_url)

    assert result.returncode == 0
    assert result.stderr == ""
    assert "Static fixture article" in result.stdout


def test_carnivore_allows_up_to_ten_redirects(fixture_server):
    result = run_carnivore(f"{fixture_server}/redirect-loop?n=10")

    assert result.returncode == 0
    assert result.stderr == ""
    assert "Static fixture article" in result.stdout


def test_carnivore_rejects_more_than_ten_redirects(fixture_server):
    result = run_carnivore(f"{fixture_server}/redirect-loop?n=11")

    assert result.returncode == 1
    assert result.stdout == ""
    assert "policy_denied" in result.stderr


def test_carnivore_rejects_non_http_redirect_target(fixture_server):
    result = run_carnivore(f"{fixture_server}/redirect-file")

    assert result.returncode == 1
    assert result.stdout == ""
    assert "policy_denied" in result.stderr


def test_carnivore_rejects_redirect_into_private_address_space(fixture_server):
    result = run_carnivore(f"{fixture_server}/redirect-private")

    assert result.returncode == 1
    assert result.stdout == ""
    assert "policy_denied" in result.stderr


def test_carnivore_reports_http_status_on_failure(http_error_url):
    result = run_carnivore(http_error_url)

    assert result.returncode == 1
    assert result.stdout == ""
    assert "http_error" in result.stderr


def test_carnivore_reports_missing_content(fixture_server):
    result = run_carnivore(f"{fixture_server}/empty")

    assert result.returncode == 1
    assert result.stdout == ""
    assert "no_content" in result.stderr


def test_carnivore_reports_document_size_limit(fixture_server):
    result = run_carnivore(f"{fixture_server}/huge-document")

    assert result.returncode == 1
    assert result.stdout == ""
    assert "resource_limit" in result.stderr


def test_carnivore_reports_subrequest_count_limit(fixture_server):
    result = run_carnivore(f"{fixture_server}/many-requests")

    assert result.returncode == 1
    assert result.stdout == ""
    assert "resource_limit" in result.stderr


def test_carnivore_reports_transfer_size_limit(fixture_server):
    result = run_carnivore(f"{fixture_server}/transfer", timeout=120)

    assert result.returncode == 1
    assert result.stdout == ""
    assert "resource_limit" in result.stderr


def test_carnivore_times_out_without_partial_output(fixture_server):
    result = run_carnivore(f"{fixture_server}/hang", "--timeout", "3", timeout=30)

    assert result.returncode == 1
    assert result.stdout == ""
    assert "timeout" in result.stderr


def test_carnivore_includes_content_from_the_settle_window(fixture_server):
    result = run_carnivore(f"{fixture_server}/javascript-early")

    assert result.returncode == 0
    assert result.stderr == ""
    assert "Early JavaScript fixture content." in result.stdout


def test_carnivore_excludes_content_after_the_settle_window(fixture_server):
    result = run_carnivore(f"{fixture_server}/javascript-late")

    assert result.returncode == 0
    assert result.stderr == ""
    assert "Late JavaScript fixture content." not in result.stdout


def test_carnivore_fixed_settle_window_survives_continuous_network_activity(
    fixture_server,
):
    baseline_started_at = time.monotonic()
    baseline_result = run_carnivore(f"{fixture_server}/article")
    baseline_elapsed = time.monotonic() - baseline_started_at

    assert baseline_result.returncode == 0
    assert baseline_result.stderr == ""

    started_at = time.monotonic()
    result = run_carnivore(
        f"{fixture_server}/continuous-network", timeout=int(baseline_elapsed) + 5
    )
    elapsed = time.monotonic() - started_at

    assert result.returncode == 0
    assert result.stderr == ""
    assert "Continuous network fixture" in result.stdout
    assert elapsed >= 2
    assert elapsed < baseline_elapsed + 1.0
