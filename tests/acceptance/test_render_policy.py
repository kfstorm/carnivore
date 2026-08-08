import pytest

from carnivore.render import (
    MAX_REDIRECTS,
    _address_allowed,
    _host_is_loopback,
    RenderPolicy,
)


@pytest.mark.parametrize(
    ("host", "expected"),
    [
        ("127.0.0.1", True),
        ("localhost", True),
        ("::1", True),
        ("127.0.0.2", True),
        ("8.8.8.8", False),
        ("example.com", False),
        ("", False),
    ],
)
def test_host_is_loopback(host, expected):
    assert _host_is_loopback(host) is expected


@pytest.mark.parametrize(
    ("address", "allow_loopback", "expected"),
    [
        ("8.8.8.8", False, True),
        ("1.1.1.1", False, True),
        ("127.0.0.1", True, True),
        ("::1", True, True),
        ("127.0.0.1", False, False),
        ("10.0.0.1", False, False),
        ("192.168.1.1", False, False),
        ("172.16.0.1", False, False),
        ("169.254.10.10", False, False),
        ("100.64.0.1", False, False),
        ("0.0.0.0", False, False),
        ("fe80::1", False, False),
    ],
)
def test_address_allowed(address, allow_loopback, expected):
    assert _address_allowed(address, allow_loopback) is expected


@pytest.mark.asyncio
async def test_render_policy_allows_initial_loopback_host():
    policy = RenderPolicy(allow_loopback=True)

    await policy.check_navigation_url("http://127.0.0.1:8080/article")

    assert policy.error is None


def test_render_policy_rejects_redirect_overage():
    policy = RenderPolicy(allow_loopback=True)

    for _ in range(MAX_REDIRECTS):
        policy.check_redirect()
        assert policy.error is None

    policy.check_redirect()

    assert policy.error is not None
    assert policy.error.code == "policy_denied"


def test_render_policy_rejects_subrequest_overage():
    policy = RenderPolicy(allow_loopback=True)

    policy.check_subrequest()
    policy.check_subrequest()

    assert policy.error is None


def test_render_document_limit_uses_stable_code():
    policy = RenderPolicy(allow_loopback=True)

    policy.check_document("x" * (10 * 1024 * 1024 + 1))

    assert policy.error is not None
    assert policy.error.code == "resource_limit"
