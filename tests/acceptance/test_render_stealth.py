from pathlib import Path

import pytest

from carnivore import render
from carnivore.models import FetchError


PROJECT_ROOT = Path(__file__).parents[2]
STEALTH_VERSION = "2.0.3"
STEALTH_WHEEL_SHA256 = "1887ade423ab7ff8ae16d363a30a38de0b5817e1e4a29d47b74bf3a0e3dbfcb"
STEALTH_SOURCE_COMMIT = "6f9dbdd25e8685a8957d2679a142cb5ba70f32a8"


class FakePage:
    def __init__(self, events):
        self.events = events
        self.main_frame = object()

    async def route(self, *_args):
        self.events.append("route")

    async def goto(self, *_args, **_kwargs):
        self.events.append("goto")

    async def content(self):
        self.events.append("content")
        return "<html><body>fixture</body></html>"


class FakeContext:
    def __init__(self, events):
        self.events = events
        self.pages = [FakePage(events)]

    def on(self, event, _handler):
        self.events.append(f"context:{event}")

    async def add_init_script(self, _script):
        self.events.append("init_script")

    async def close(self):
        self.events.append("close")


class FakePlaywright:
    def __init__(self, events, context):
        self.events = events
        self.context = context
        self.chromium = self

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        self.events.append("playwright_close")

    async def launch_persistent_context(self, *_args, **_kwargs):
        self.events.append("launch")
        return self.context


class FakeStealth:
    def __init__(self, events, fail=False):
        self.events = events
        self.fail = fail
        self.events.append("stealth_construct")

    async def apply_stealth_async(self, context):
        self.events.append("stealth_apply")
        if self.fail:
            raise RuntimeError("stealth setup failed")
        await context.add_init_script("fixture")


def _patch_browser(monkeypatch, events, *, stealth_failure=False):
    context = FakeContext(events)
    playwright = FakePlaywright(events, context)
    monkeypatch.setattr(render, "async_playwright", lambda: playwright)
    monkeypatch.setattr(
        render,
        "Stealth",
        lambda: FakeStealth(events, fail=stealth_failure),
    )

    async def skip_settle(_seconds):
        return None

    monkeypatch.setattr(render.asyncio, "sleep", skip_settle)


@pytest.mark.asyncio
async def test_render_applies_stealth_before_route_and_first_navigation(monkeypatch):
    events = []
    _patch_browser(monkeypatch, events)

    await render.render_browser("http://127.0.0.1:8080/article", timeout=5)

    assert events.index("launch") < events.index("stealth_apply")
    assert events.index("stealth_apply") < events.index("route")
    assert events.index("stealth_apply") < events.index("goto")
    assert events.count("goto") == 1


@pytest.mark.asyncio
async def test_render_fails_closed_when_stealth_initialization_fails(monkeypatch):
    events = []
    _patch_browser(monkeypatch, events, stealth_failure=True)

    with pytest.raises(
        FetchError, match="internal_error: Stealth initialization failed"
    ):
        await render.render_browser("http://127.0.0.1:8080/article", timeout=5)

    assert "goto" not in events
    assert "route" not in events
    assert "close" in events


def test_core_stealth_dependency_is_stable_and_auditable():
    requirements = (PROJECT_ROOT / "docker/requirements-core.txt").read_text()
    lock = (PROJECT_ROOT / "docker/core.lock").read_text()

    assert (
        f"playwright-stealth=={STEALTH_VERSION} --hash=sha256:{STEALTH_WHEEL_SHA256}"
        in requirements
    )
    assert f"PLAYWRIGHT_STEALTH_VERSION={STEALTH_VERSION}" in lock
    assert f"PLAYWRIGHT_STEALTH_WHEEL_SHA256={STEALTH_WHEEL_SHA256}" in lock
    assert f"PLAYWRIGHT_STEALTH_SOURCE_COMMIT={STEALTH_SOURCE_COMMIT}" in lock
    assert "playwright_stealth@rc4" not in requirements
