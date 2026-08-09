#!/usr/bin/env python3

"""Run the frozen offline fetch corpus and compare release evidence."""

import argparse
import json
import math
import os
import subprocess
import sys
import time
from contextlib import contextmanager
from pathlib import Path
from statistics import mean, median
from threading import Thread
from typing import Iterator

from ruamel.yaml import YAML


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MAX_OUTPUT_BYTES = 10 * 1024 * 1024
QUALITY_FIELDS = (
    "body_anchor_rate",
    "forbidden_rate",
    "structure_rate",
    "metadata_rate",
)
BENCHMARK_MODES = ("source", "image")


def percentile(values: list[float], probability: float) -> float:
    """Return a linearly interpolated percentile for a non-empty sample."""
    if not values:
        raise ValueError("cannot calculate a percentile for an empty sample")
    if not 0 <= probability <= 1:
        raise ValueError("probability must be between zero and one")
    ordered = sorted(values)
    position = (len(ordered) - 1) * probability
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return float(ordered[lower])
    fraction = position - lower
    return float(ordered[lower] + (ordered[upper] - ordered[lower]) * fraction)


def load_corpus(path: Path) -> list[dict]:
    document = YAML(typ="safe").load(path.read_text(encoding="utf-8"))
    if not isinstance(document, dict) or document.get("schema_version") != 1:
        raise ValueError("corpus must use schema_version 1")
    cases = document.get("cases")
    if not isinstance(cases, list) or not cases:
        raise ValueError("corpus must define at least one case")

    validated = []
    seen_ids = set()
    for case in cases:
        if not isinstance(case, dict):
            raise ValueError("each corpus case must be a mapping")
        case_id = case.get("id")
        if not isinstance(case_id, str) or not case_id or case_id in seen_ids:
            raise ValueError("corpus case ids must be unique non-empty strings")
        if not isinstance(case.get("path"), str) or not case["path"].startswith("/"):
            raise ValueError(f"corpus case {case_id} must use an absolute fixture path")
        if case.get("format") not in ("markdown", "html", "full_html"):
            raise ValueError(f"corpus case {case_id} uses an unsupported format")
        if case.get("resource_mode") not in ("omit", "link", "embed"):
            raise ValueError(f"corpus case {case_id} uses an unsupported resource mode")
        for field in ("body_anchors", "forbidden", "structure", "metadata"):
            values = case.get(field, [])
            if not isinstance(values, list) or not all(
                isinstance(value, str) for value in values
            ):
                raise ValueError(f"corpus case {case_id} has invalid {field}")
        validated.append(
            {
                **case,
                "body_anchors": case.get("body_anchors", []),
                "forbidden": case.get("forbidden", []),
                "structure": case.get("structure", []),
                "metadata": case.get("metadata", []),
            }
        )
        seen_ids.add(case_id)
    return validated


@contextmanager
def fixture_server() -> Iterator[str]:
    sys.path.insert(0, str(PROJECT_ROOT / "tests" / "acceptance"))
    from fixture_server import FixtureHandler
    from http.server import ThreadingHTTPServer

    server = ThreadingHTTPServer(("127.0.0.1", 0), FixtureHandler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        thread.join()
        server.server_close()


def _command_for_case(case: dict, url: str, image: str | None) -> list[str]:
    arguments = [
        url,
        "--format",
        case["format"],
        "--resource-mode",
        case["resource_mode"],
        "--output",
        "json",
        "--timeout",
        str(case.get("timeout", 30)),
    ]
    if image:
        return [
            "docker",
            "run",
            "--rm",
            "--network",
            "host",
            "--env",
            "CARNIVORE_CACHE=0",
            image,
            *arguments,
        ]
    return [sys.executable, "-m", "carnivore", *arguments]


def _run_case(case: dict, base_url: str, image: str | None) -> dict:
    command = _command_for_case(case, f"{base_url}{case['path']}", image)
    environment = os.environ.copy()
    environment["CARNIVORE_CACHE"] = "0"
    package_path = str(PROJECT_ROOT / "carnivore-lib")
    environment["PYTHONPATH"] = os.pathsep.join(
        path for path in (package_path, environment.get("PYTHONPATH")) if path
    )
    timeout = float(case.get("timeout", 30)) + 10
    started = time.perf_counter()
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=False,
            env=environment,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return {"duration": time.perf_counter() - started, "error": "timeout"}

    duration = time.perf_counter() - started
    if completed.returncode != 0:
        try:
            error = json.loads(completed.stdout).get("error", {}).get("code")
        except (TypeError, json.JSONDecodeError):
            error = None
        return {
            "duration": duration,
            "error": error or "command_failed",
        }
    try:
        envelope = json.loads(completed.stdout)
    except json.JSONDecodeError:
        return {"duration": duration, "error": "invalid_json"}
    if envelope.get("ok") is not True:
        return {"duration": duration, "error": "fetch_failed"}
    content = envelope.get("content")
    metadata = envelope.get("metadata")
    if not isinstance(content, str) or not isinstance(metadata, dict):
        return {"duration": duration, "error": "invalid_result"}

    quality = {
        "body_anchor_rate": all(anchor in content for anchor in case["body_anchors"]),
        "forbidden_rate": all(
            fragment not in content for fragment in case["forbidden"]
        ),
        "structure_rate": all(fragment in content for fragment in case["structure"]),
        "metadata_rate": all(
            metadata.get(key) not in (None, "") for key in case["metadata"]
        ),
    }
    return {
        "duration": duration,
        "size": len(content.encode("utf-8")),
        "quality": quality,
    }


def _quality_rates(samples: list[dict]) -> dict[str, float]:
    return {
        field: mean(float(sample["quality"][field]) for sample in samples)
        for field in QUALITY_FIELDS
    }


def run_benchmark(cases: list[dict], runs: int, image: str | None = None) -> dict:
    if runs <= 0:
        raise ValueError("runs must be positive")
    samples = {case["id"]: [] for case in cases}
    total_durations = []
    with fixture_server() as base_url:
        for _ in range(runs):
            started = time.perf_counter()
            for case in cases:
                sample = _run_case(case, base_url, image)
                if "quality" not in sample:
                    sample["quality"] = {field: False for field in QUALITY_FIELDS}
                samples[case["id"]].append(sample)
            total_durations.append(time.perf_counter() - started)

    case_results = {}
    all_samples = [sample for case in cases for sample in samples[case["id"]]]
    for case in cases:
        case_samples = samples[case["id"]]
        durations = [sample["duration"] for sample in case_samples]
        sizes = [sample.get("size", 0) for sample in case_samples]
        case_results[case["id"]] = {
            "duration_seconds": {
                "median": median(durations),
                "p95": percentile(durations, 0.95),
            },
            "output_bytes": {
                "median": median(sizes),
                "max": max(sizes),
            },
            "quality": _quality_rates(case_samples),
            "failures": sum("error" in sample for sample in case_samples),
        }
    return {
        "mode": "image" if image else "source",
        "schema_version": 1,
        "runs": runs,
        "cases": case_results,
        "totals": {
            "duration_seconds": {
                "median": median(total_durations),
                "p95": percentile(total_durations, 0.95),
            },
            "quality": _quality_rates(all_samples),
            "failures": sum("error" in sample for sample in all_samples),
        },
    }


def _comparison_error(comparison: dict, message: str) -> None:
    comparison["errors"].append(message)


def compare_results(candidate: dict, baseline: dict) -> dict:
    comparison = {
        "quality_regressions": [],
        "timing_regressions": [],
        "size_reviews": [],
        "size_limit_failures": [],
        "errors": [],
        "review_required": False,
        "blocking": False,
    }
    candidate_mode = candidate.get("mode")
    baseline_mode = baseline.get("mode")
    if candidate_mode not in BENCHMARK_MODES:
        _comparison_error(
            comparison,
            f"candidate benchmark mode is missing or invalid: {candidate_mode!r}",
        )
    if baseline_mode not in BENCHMARK_MODES:
        _comparison_error(
            comparison,
            f"baseline benchmark mode is missing or invalid: {baseline_mode!r}",
        )
    if (
        candidate_mode in BENCHMARK_MODES
        and baseline_mode in BENCHMARK_MODES
        and candidate_mode != baseline_mode
    ):
        _comparison_error(
            comparison,
            "benchmark execution mode mismatch: "
            f"candidate={candidate_mode}, baseline={baseline_mode}",
        )
    baseline_cases = baseline.get("cases", {})
    for case_id, candidate_case in candidate.get("cases", {}).items():
        baseline_case = baseline_cases.get(case_id)
        if not isinstance(baseline_case, dict):
            _comparison_error(comparison, f"baseline is missing case {case_id}")
            continue
        candidate_quality = candidate_case.get("quality", {})
        baseline_quality = baseline_case.get("quality", {})
        for field in QUALITY_FIELDS:
            current = candidate_quality.get(field)
            previous = baseline_quality.get(field)
            if not isinstance(current, (int, float)) or not isinstance(
                previous, (int, float)
            ):
                _comparison_error(
                    comparison, f"missing quality metric {case_id}/{field}"
                )
            elif current < previous:
                comparison["quality_regressions"].append(
                    {
                        "case": case_id,
                        "metric": field,
                        "baseline": previous,
                        "candidate": current,
                    }
                )

        candidate_size = candidate_case.get("output_bytes", {}).get("median")
        candidate_max_size = candidate_case.get("output_bytes", {}).get("max")
        baseline_size = baseline_case.get("output_bytes", {}).get("median")
        if (
            isinstance(candidate_max_size, (int, float))
            and candidate_max_size > MAX_OUTPUT_BYTES
        ):
            comparison["size_limit_failures"].append(
                {"case": case_id, "bytes": candidate_max_size}
            )
        if not isinstance(candidate_size, (int, float)) or not isinstance(
            baseline_size, (int, float)
        ):
            _comparison_error(comparison, f"missing output size metric for {case_id}")
        elif (
            abs(candidate_size - baseline_size) / baseline_size > 0.25
            if baseline_size
            else candidate_size > 0
        ):
            comparison["size_reviews"].append(
                {
                    "case": case_id,
                    "baseline": baseline_size,
                    "candidate": candidate_size,
                    "change": candidate_size / baseline_size - 1
                    if baseline_size
                    else None,
                }
            )

        if candidate_case.get("failures", 0):
            comparison["errors"].append(
                f"{case_id} had {candidate_case['failures']} failed runs"
            )

    candidate_total = candidate.get("totals", {})
    baseline_total = baseline.get("totals", {})
    candidate_quality = candidate_total.get("quality", {})
    baseline_quality = baseline_total.get("quality", {})
    for field in QUALITY_FIELDS:
        current = candidate_quality.get(field)
        previous = baseline_quality.get(field)
        if not isinstance(current, (int, float)) or not isinstance(
            previous, (int, float)
        ):
            _comparison_error(comparison, f"missing total quality metric {field}")
        elif current < previous:
            comparison["quality_regressions"].append(
                {
                    "case": "total",
                    "metric": field,
                    "baseline": previous,
                    "candidate": current,
                }
            )

    candidate_timing = candidate_total.get("duration_seconds", {})
    baseline_timing = baseline_total.get("duration_seconds", {})
    candidate_median = candidate_timing.get("median")
    baseline_median = baseline_timing.get("median")
    candidate_p95 = candidate_timing.get("p95")
    baseline_p95 = baseline_timing.get("p95")
    if not all(
        isinstance(value, (int, float))
        for value in (
            candidate_median,
            baseline_median,
            candidate_p95,
            baseline_p95,
        )
    ):
        _comparison_error(comparison, "missing total timing metrics")
    else:
        median_change = candidate_median / baseline_median - 1 if baseline_median else 0
        p95_change = candidate_p95 / baseline_p95 - 1 if baseline_p95 else 0
        if median_change > 0.20 and candidate_median - baseline_median > 1:
            comparison["timing_regressions"].append(
                {
                    "metric": "median_total_seconds",
                    "baseline": baseline_median,
                    "candidate": candidate_median,
                    "change": median_change,
                }
            )
        if p95_change > 0.30:
            comparison["timing_regressions"].append(
                {
                    "metric": "p95_total_seconds",
                    "baseline": baseline_p95,
                    "candidate": candidate_p95,
                    "change": p95_change,
                }
            )

    comparison["review_required"] = bool(comparison["size_reviews"])
    comparison["blocking"] = bool(
        comparison["quality_regressions"]
        or comparison["timing_regressions"]
        or comparison["size_limit_failures"]
        or comparison["errors"]
    )
    return comparison


def _summary(result: dict) -> str:
    total = result["totals"]["duration_seconds"]
    lines = [
        f"Benchmark: {result['version']} ({result['runs']} runs)",
        f"Total time: median={total['median']:.2f}s p95={total['p95']:.2f}s",
        f"Failures: {result['totals']['failures']}",
    ]
    for case_id, case in result["cases"].items():
        size = case["output_bytes"]
        lines.append(
            f"- {case_id}: median={case['duration_seconds']['median']:.2f}s "
            f"size={size['median']:.0f}B quality="
            f"{min(case['quality'].values()):.2f}"
        )
    comparison = result.get("comparison")
    if comparison:
        lines.append(
            "Comparison: "
            f"blocking={comparison['blocking']} "
            f"review_required={comparison['review_required']}"
        )
        if comparison["review_required"]:
            lines.append(
                "::warning::Output size changed by more than 25%; review required"
            )
    return "\n".join(lines)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Benchmark the frozen offline corpus")
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--runs", type=int, default=5)
    parser.add_argument("--baseline", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--image", default=os.environ.get("CARNIVORE_BENCHMARK_IMAGE"))
    parser.add_argument(
        "--version", default=os.environ.get("GITHUB_SHA", "working-tree")
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="fail when quality, size, or performance gates regress",
    )
    return parser


def main(argv=None) -> int:
    args = _parser().parse_args(argv)
    try:
        cases = load_corpus(args.corpus)
        result = run_benchmark(cases, args.runs, args.image)
        result["version"] = args.version
        if args.baseline:
            baseline = json.loads(args.baseline.read_text(encoding="utf-8"))
            result["comparison"] = compare_results(result, baseline)
        elif args.strict:
            result["comparison"] = {
                "quality_regressions": [],
                "timing_regressions": [],
                "size_reviews": [],
                "size_limit_failures": [],
                "errors": ["baseline is required in strict mode"],
                "review_required": False,
                "blocking": True,
            }
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(
            json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    except (OSError, TypeError, ValueError, json.JSONDecodeError) as error:
        print(f"benchmark failed: {error}", file=sys.stderr)
        return 2

    print(_summary(result))
    if args.strict and result.get("comparison", {}).get("blocking"):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
