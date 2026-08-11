import asyncio
from pathlib import Path

import pytest

from carnivore import render
from carnivore.models import FetchError


PROJECT_ROOT = Path(__file__).parents[2]
REAL_SLEEP = asyncio.sleep
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
    def __init__(self, events, close_delay=0, injection_failure=False):
        self.events = events
        self.close_delay = close_delay
        self.injection_failure = injection_failure
        self.pages = [FakePage(events)]

    def on(self, event, _handler):
        self.events.append(f"context:{event}")

    async def add_init_script(self, _script):
        self.events.append("init_script")
        if self.injection_failure:
            raise RuntimeError("injection failed")

    async def close(self):
        self.events.append("close_started")
        if self.close_delay:
            await REAL_SLEEP(self.close_delay)
        self.events.append("close")


class FakePlaywright:
    def __init__(self, events, context):
        self.events = events
        self.context = context
        self.chromium = self
        self.launch_kwargs = None

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        self.events.append("playwright_close")

    async def launch_persistent_context(self, *_args, **_kwargs):
        self.events.append("launch")
        self.launch_kwargs = _kwargs
        return self.context


class FakeStealth:
    def __init__(self, events, fail=False, script_failure=False, delay=0, **kwargs):
        self.events = events
        self.delay = delay
        self.fail = fail
        self.script_failure = script_failure
        self.kwargs = kwargs
        self.events.append("stealth_construct")

    async def apply_stealth_async(self, context):
        self.events.append("stealth_apply")
        if self.delay:
            await REAL_SLEEP(self.delay)
        if self.fail:
            raise RuntimeError("stealth setup failed")
        if self.script_failure:
            raise RuntimeError("script generation failed")
        await context.add_init_script("fixture")


def _patch_browser(
    monkeypatch,
    events,
    *,
    stealth_failure=False,
    stealth_construction_failure=False,
    stealth_script_failure=False,
    stealth_delay=0,
    close_delay=0,
    injection_failure=False,
):
    context = FakeContext(
        events,
        close_delay=close_delay,
        injection_failure=injection_failure,
    )
    playwright = FakePlaywright(events, context)
    stealth_kwargs = {}
    monkeypatch.setattr(render, "async_playwright", lambda: playwright)

    def make_stealth(**kwargs):
        stealth_kwargs.update(kwargs)
        if stealth_construction_failure:
            raise RuntimeError("stealth construction failed")
        return FakeStealth(
            events,
            fail=stealth_failure,
            script_failure=stealth_script_failure,
            delay=stealth_delay,
            **kwargs,
        )

    monkeypatch.setattr(
        render,
        "Stealth",
        make_stealth,
    )

    async def skip_settle(_seconds):
        return None

    monkeypatch.setattr(render.asyncio, "sleep", skip_settle)
    return playwright, stealth_kwargs


@pytest.mark.asyncio
async def test_render_applies_stealth_before_route_and_first_navigation(monkeypatch):
    events = []
    playwright, _ = _patch_browser(monkeypatch, events)

    await render.render_browser("http://127.0.0.1:8080/article", timeout=5)

    assert events.index("launch") < events.index("stealth_apply")
    assert events.index("stealth_apply") < events.index("route")
    assert events.index("stealth_apply") < events.index("goto")
    assert events.count("goto") == 1


@pytest.mark.asyncio
async def test_render_uses_one_chrome_130_mac_identity_and_strict_tls(monkeypatch):
    events = []
    playwright, stealth_kwargs = _patch_browser(monkeypatch, events)

    await render.render_browser("https://example.com/article", timeout=5)

    assert playwright.launch_kwargs == {
        "channel": "chromium",
        "user_agent": render.USER_AGENT,
        "extra_http_headers": render.EXTRA_HTTP_HEADERS,
        "ignore_https_errors": False,
    }
    assert stealth_kwargs == {
        "navigator_platform_override": "MacIntel",
        "navigator_user_agent_override": render.USER_AGENT,
    }


@pytest.mark.asyncio
async def test_stealth_setup_uses_the_renderer_deadline(monkeypatch):
    events = []
    _patch_browser(monkeypatch, events, stealth_delay=0.05)

    with pytest.raises(FetchError, match="timeout: Timed out after 0.01 seconds"):
        await render.render_browser("http://127.0.0.1:8080/article", timeout=0.01)

    assert "goto" not in events


@pytest.mark.asyncio
async def test_stealth_failure_cleanup_does_not_use_a_fixed_timeout(
    monkeypatch, capsys
):
    events = []
    _patch_browser(monkeypatch, events, stealth_failure=True, close_delay=0.05)
    removed_profiles = []
    wait_for_timeouts = []
    real_wait_for = asyncio.wait_for

    async def record_wait_for(awaitable, *, timeout):
        wait_for_timeouts.append(timeout)
        return await real_wait_for(awaitable, timeout=timeout)

    monkeypatch.setattr(render.asyncio, "wait_for", record_wait_for)
    monkeypatch.setattr(
        render.shutil,
        "rmtree",
        lambda path, ignore_errors: removed_profiles.append(path),
    )

    with pytest.raises(
        FetchError, match="internal_error: Stealth initialization failed"
    ):
        await render.render_browser("http://127.0.0.1:8080/article", timeout=0.2)

    assert "goto" not in events
    assert "close_started" in events
    assert "close" in events
    assert len(removed_profiles) == 1
    assert max(wait_for_timeouts) < 0.2
    assert capsys.readouterr().out == ""


@pytest.mark.asyncio
async def test_stealth_import_failure_is_normalized(monkeypatch):
    events = []
    _patch_browser(monkeypatch, events)
    monkeypatch.setattr(render, "Stealth", None)

    with pytest.raises(
        FetchError, match="internal_error: Stealth initialization failed"
    ):
        await render.render_browser("http://127.0.0.1:8080/article", timeout=5)

    assert "goto" not in events
    assert "route" not in events
    assert events.count("launch") == 1
    assert "close" in events


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "failure_options",
    [
        {"stealth_construction_failure": True},
        {"stealth_script_failure": True},
        {"injection_failure": True},
    ],
)
async def test_stealth_setup_failure_is_normalized(monkeypatch, failure_options):
    events = []
    _patch_browser(monkeypatch, events, **failure_options)

    with pytest.raises(
        FetchError, match="internal_error: Stealth initialization failed"
    ):
        await render.render_browser("http://127.0.0.1:8080/article", timeout=5)

    assert "goto" not in events
    assert "route" not in events
    assert events.count("launch") == 1
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
    assert "PLAYWRIGHT_STEALTH_LICENSE=MIT" in lock
    assert "playwright_stealth@rc4" not in requirements
