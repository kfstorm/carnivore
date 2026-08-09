import argparse
import base64
import socket
import ssl
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit


PIXEL_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMBAAZnGfoAAAAASUVORK5CYII="
)
CHUNK_BYTES = b"x" * (10 * 1024 * 1024)
HUGE_DOCUMENT = (
    "<!doctype html><html><head><title>Huge document</title></head><body>"
    + "<!-- filler -->" * 800000
    + "</body></html>"
)


def article(title, body, script=""):
    return f"""<!doctype html>
<html>
  <head><title>{title}</title></head>
  <body>
    <main>
      <article>
        <h1>{title}</h1>
        <p>{body}</p>
        <p>The fixture uses stable local HTML so acceptance tests can assert semantic
        output without depending on external websites or variable page sizes.</p>
      </article>
    </main>
    {script}
  </body>
</html>"""


class FixtureHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        path = urlsplit(self.path).path

        if path == "/redirect":
            self.send_response(302)
            self.send_header("Location", "/article")
            self.end_headers()
            return

        if path == "/server-error":
            self.send_error(500)
            return

        if path == "/pixel.png":
            self.send_response(200)
            self.send_header("Content-Type", "image/png")
            self.send_header("Content-Length", str(len(PIXEL_PNG)))
            self.end_headers()
            self.wfile.write(PIXEL_PNG)
            return

        if path == "/poll":
            self.send_response(204)
            self.end_headers()
            return

        if path == "/redirect-loop":
            remaining = int(parse_qs(urlsplit(self.path).query).get("n", ["0"])[0])
            if remaining > 1:
                self.send_response(302)
                self.send_header("Location", f"/redirect-loop?n={remaining - 1}")
                self.end_headers()
                return
            self.send_response(302)
            self.send_header("Location", "/article")
            self.end_headers()
            return

        if path == "/redirect-file":
            self.send_response(302)
            self.send_header("Location", "file:///etc/hostname")
            self.end_headers()
            return

        if path == "/redirect-private":
            self.send_response(302)
            self.send_header("Location", "http://10.255.255.1/")
            self.end_headers()
            return

        if path == "/hang":
            time.sleep(300)
            return

        if path == "/delayed":
            time.sleep(0.25)
            content = article(
                "Delayed fixture article",
                "This article is served after a deterministic delay.",
            )
        elif path == "/javascript-early":
            content = article(
                "Early JavaScript fixture",
                "This article receives additional content shortly after "
                "DOMContentLoaded.",
                """<script>
setTimeout(() => {
  document.querySelector("article").insertAdjacentHTML(
    "beforeend", "<p>Early JavaScript fixture content.</p>"
  );
}, 100);
</script>""",
            )
        elif path == "/javascript-late":
            content = article(
                "Late JavaScript fixture",
                "This article receives additional content after the fixed settle "
                "window.",
                """<script>
setTimeout(() => {
  document.querySelector("article").insertAdjacentHTML(
    "beforeend", "<p>Late JavaScript fixture content.</p>"
  );
}, 3000);
</script>""",
            )
        elif path == "/empty":
            content = "<!doctype html><html><body></body></html>"
        elif path == "/resources":
            content = article(
                "Resource fixture article",
                "This article contains a local image for resource-mode acceptance "
                "tests.",
            ).replace(
                "</article>", '<img src="/pixel.png" alt="fixture pixel"></article>'
            )
        elif path == "/host":
            content = article(
                "Host header fixture",
                f"The request Host header was {self.headers.get('Host', '')}.",
            )
        elif path == "/continuous-network":
            content = article(
                "Continuous network fixture",
                "This article keeps making local requests after it is rendered.",
                "<script>setInterval(() => fetch('/poll'), 100);</script>",
            )
        elif path == "/huge-document":
            content = HUGE_DOCUMENT
        elif path == "/many-requests":
            scripts = "".join(f'<script src="/sub/{i}"></script>' for i in range(220))
            content = f"<!doctype html><html><body>{scripts}</body></html>"
        elif path == "/transfer":
            scripts = "".join(f'<script src="/chunk/{i}"></script>' for i in range(6))
            content = f"<!doctype html><html><body>{scripts}</body></html>"
        elif path.startswith("/sub/"):
            self.send_response(200)
            self.send_header("Content-Type", "application/javascript")
            self.send_header("Content-Length", "5")
            self.end_headers()
            self.wfile.write(b"/*x*/")
            return
        elif path.startswith("/chunk/"):
            self.send_response(200)
            self.send_header("Content-Type", "application/javascript")
            self.send_header("Content-Length", str(len(CHUNK_BYTES)))
            self.end_headers()
            self.wfile.write(CHUNK_BYTES)
            return
        elif path == "/article":
            content = article(
                "Static fixture article",
                "This deterministic local article has enough text for Readability "
                "to identify it as the primary content. It is served without "
                "external dependencies so the acceptance suite can exercise the "
                "existing fetch command through a real browser.",
            )
        else:
            self.send_error(404)
            return

        encoded_content = content.encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded_content)))
        self.end_headers()
        self.wfile.write(encoded_content)

    def log_message(self, format, *args):
        pass


class IPv6ThreadingHTTPServer(ThreadingHTTPServer):
    address_family = socket.AF_INET6


def run_server(
    port: int,
    host: str = "127.0.0.1",
    certfile: str | None = None,
    keyfile: str | None = None,
) -> None:
    server_type = IPv6ThreadingHTTPServer if ":" in host else ThreadingHTTPServer
    server = server_type((host, port), FixtureHandler)
    if certfile and keyfile:
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(certfile, keyfile)
        server.socket = context.wrap_socket(server.socket, server_side=True)
    try:
        server.serve_forever()
    finally:
        server.shutdown()
        server.server_close()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Serve deterministic Carnivore fixtures"
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--cert")
    parser.add_argument("--key")
    args = parser.parse_args()
    if bool(args.cert) != bool(args.key):
        parser.error("--cert and --key must be provided together")
    run_server(args.port, args.host, args.cert, args.key)


if __name__ == "__main__":
    main()
