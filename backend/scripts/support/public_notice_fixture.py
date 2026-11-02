"""Relay only public fixture notices to browser tests; never relay JWT headers."""

import json
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread
from urllib.parse import parse_qs, urlsplit


@contextmanager
def public_notice_fixture(twitch_state):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_GET(self):
            try:
                after = max(0, int(parse_qs(urlsplit(self.path).query).get("after", ["0"])[0]))
            except ValueError:
                self.send_response(400)
                self.end_headers()
                return
            records = list(twitch_state["messages"])
            notices = [json.loads(record["body"]["message"]) for record in records[after:]]
            assert all(set(event) == {"event", "channel_id", "version"} for event in notices)
            body = json.dumps({"cursor": len(records), "events": notices}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}/public-notices"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
