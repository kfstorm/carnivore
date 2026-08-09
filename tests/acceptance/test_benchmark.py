from copy import deepcopy
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[2] / "scripts"))

from benchmark import (  # noqa: E402
    MAX_OUTPUT_BYTES,
    compare_results,
    load_corpus,
    percentile,
)


def _result(
    median_time=10.0,
    p95_time=10.0,
    quality=1.0,
    size=100,
    mode="source",
):
    quality_metrics = {
        "body_anchor_rate": quality,
        "forbidden_rate": quality,
        "metadata_rate": quality,
        "structure_rate": quality,
    }
    case = {
        "duration_seconds": {"median": median_time, "p95": p95_time},
        "failures": 0,
        "output_bytes": {"max": size, "median": size},
        "quality": quality_metrics,
    }
    return {
        "mode": mode,
        "cases": {"case": deepcopy(case)},
        "runs": 5,
        "schema_version": 1,
        "totals": {
            "duration_seconds": {"median": median_time, "p95": p95_time},
            "failures": 0,
            "quality": quality_metrics,
        },
    }


def test_percentile_uses_interpolation_for_five_runs():
    assert percentile([1, 2, 3, 4, 5], 0.95) == 4.8


def test_corpus_contains_frozen_fixture_cases():
    cases = load_corpus(Path("benchmarks/corpus.yml"))

    assert len(cases) == 5
    assert {case["resource_mode"] for case in cases} == {"omit", "link", "embed"}


def test_comparison_requires_quality_and_performance_confirmation():
    baseline = _result()
    candidate = _result(median_time=12.1, p95_time=13.1, quality=0.9)

    comparison = compare_results(candidate, baseline)

    assert comparison["quality_regressions"]
    assert comparison["timing_regressions"]
    assert comparison["blocking"] is True


def test_comparison_rejects_different_execution_modes():
    comparison = compare_results(_result(mode="image"), _result(mode="source"))

    assert comparison["errors"] == [
        "benchmark execution mode mismatch: candidate=image, baseline=source"
    ]
    assert comparison["blocking"] is True


def test_output_limit_is_hard_even_when_median_is_small():
    baseline = _result()
    candidate = _result(size=100)
    candidate["cases"]["case"]["output_bytes"]["max"] = MAX_OUTPUT_BYTES + 1

    comparison = compare_results(candidate, baseline)

    assert comparison["size_limit_failures"] == [
        {"case": "case", "bytes": MAX_OUTPUT_BYTES + 1}
    ]


def test_large_size_change_requires_review_without_failing_the_gate():
    comparison = compare_results(_result(size=126), _result(size=100))

    assert comparison["review_required"] is True
    assert comparison["blocking"] is False


def test_large_size_reduction_also_requires_review():
    comparison = compare_results(_result(size=74), _result(size=100))

    assert comparison["review_required"] is True
    assert comparison["blocking"] is False
