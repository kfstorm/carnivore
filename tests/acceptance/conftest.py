from threading import Thread
from http.server import ThreadingHTTPServer

import pytest

from fixture_server import FixtureHandler


@pytest.fixture
def fixture_server():
    server = ThreadingHTTPServer(("127.0.0.1", 0), FixtureHandler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        thread.join()
        server.server_close()


@pytest.fixture
def static_article_url(fixture_server):
    return f"{fixture_server}/article"


@pytest.fixture
def redirect_article_url(fixture_server):
    return f"{fixture_server}/redirect"


@pytest.fixture
def http_error_url(fixture_server):
    return f"{fixture_server}/server-error"
