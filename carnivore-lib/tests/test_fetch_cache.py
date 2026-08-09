import json

import pytest

from carnivore.models import FetchRequest, FetchResult
from carnivore.pipeline import FetchPipeline, _cache_key


@pytest.mark.asyncio
async def test_cache_is_opt_in_and_stores_final_result(monkeypatch, tmp_path):
    calls = 0

    async def fetch_result(self, request):
        nonlocal calls
        calls += 1
        return FetchResult(request.format, "cached content", {"title": "Article"})

    monkeypatch.setattr(FetchPipeline, "_fetch_within_budget", fetch_result)
    monkeypatch.setenv("CARNIVORE_CACHE_DIR", str(tmp_path))
    request = FetchRequest("https://example.com/article")
    pipeline = FetchPipeline()

    await pipeline.fetch(request)
    await pipeline.fetch(request)
    assert calls == 2
    assert not list(tmp_path.glob("*.json"))

    monkeypatch.setenv("CARNIVORE_CACHE", "1")
    await pipeline.fetch(request)
    await pipeline.fetch(request)
    assert calls == 3
    assert len(list(tmp_path.glob("*.json"))) == 1


@pytest.mark.asyncio
async def test_cache_hit_returns_without_running_pipeline(monkeypatch, tmp_path):
    monkeypatch.setenv("CARNIVORE_CACHE", "1")
    monkeypatch.setenv("CARNIVORE_CACHE_DIR", str(tmp_path))
    request = FetchRequest(
        "https://example.com/article", format="html", resource_mode="link"
    )
    expected = FetchResult("html", "<article>cached</article>", {"title": "Article"})
    from carnivore.cache import write_fetch_result

    write_fetch_result(_cache_key(request), expected)

    async def fail(*args):
        raise AssertionError("cache miss started the fetch pipeline")

    monkeypatch.setattr(FetchPipeline, "_fetch_within_budget", fail)
    assert await FetchPipeline().fetch(request) == expected


@pytest.mark.asyncio
async def test_cache_trace_reports_only_explicit_cache_hits(
    monkeypatch, tmp_path, capsys
):
    monkeypatch.setenv("CARNIVORE_CACHE", "1")
    monkeypatch.setenv("CARNIVORE_CACHE_DIR", str(tmp_path))
    request = FetchRequest("https://example.com/article")
    expected = FetchResult("markdown", "cached", {"title": "Article"})
    from carnivore.cache import write_fetch_result

    write_fetch_result(_cache_key(request), expected)
    monkeypatch.setattr(
        FetchPipeline,
        "_fetch_within_budget",
        lambda *args: pytest.fail("cache hit started the fetch pipeline"),
    )

    assert await FetchPipeline().fetch(request) == expected
    assert capsys.readouterr().err == ""

    monkeypatch.setenv("CARNIVORE_CACHE_TRACE", "1")
    assert await FetchPipeline().fetch(request) == expected
    assert capsys.readouterr().err == "cache_hit\n"


@pytest.mark.asyncio
async def test_corrupt_cache_and_legacy_pickle_are_ignored(monkeypatch, tmp_path):
    monkeypatch.setenv("CARNIVORE_CACHE", "1")
    monkeypatch.setenv("CARNIVORE_CACHE_DIR", str(tmp_path))
    request = FetchRequest("https://example.com/article")
    cache_file = tmp_path / f"{_cache_key(request)}.json"
    cache_file.write_text("not json", encoding="utf-8")
    (tmp_path / f"{_cache_key(request)}.pickle").write_bytes(b"legacy")

    async def fetch_result(self, request):
        return FetchResult(request.format, "fresh", {})

    monkeypatch.setattr(FetchPipeline, "_fetch_within_budget", fetch_result)
    assert (await FetchPipeline().fetch(request)).content == "fresh"
    envelope = json.loads(cache_file.read_text(encoding="utf-8"))
    assert envelope["payload"]["content"] == "fresh"
