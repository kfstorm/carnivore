from urllib.request import urlopen

import pytest


@pytest.mark.parametrize(
    ("path", "expected_content"),
    [
        ("/article", "Static fixture article"),
        ("/javascript-early", "Early JavaScript fixture"),
        ("/javascript-late", "Late JavaScript fixture"),
        ("/delayed", "Delayed fixture article"),
        ("/resources", "Resource fixture article"),
        ("/continuous-network", "Continuous network fixture"),
    ],
)
def test_fixture_server_provides_deterministic_scenarios(
    fixture_server, path, expected_content
):
    with urlopen(f"{fixture_server}{path}", timeout=3) as response:
        content = response.read().decode()

    assert response.status == 200
    assert expected_content in content


def test_fixture_server_provides_an_empty_document(fixture_server):
    with urlopen(f"{fixture_server}/empty", timeout=3) as response:
        content = response.read().decode()

    assert response.status == 200
    assert "<body></body>" in content


def test_fixture_server_preserves_the_request_host_header(fixture_server):
    with urlopen(f"{fixture_server}/host", timeout=3) as response:
        content = response.read().decode()

    assert response.status == 200
    assert "Host header fixture" in content
    assert fixture_server.split("://", 1)[1] in content
