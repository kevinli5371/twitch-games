"""Loopback-only HTTP Twitch stand-in for integration tests, never production auth."""

import json
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread
from urllib.parse import parse_qs, urlencode, urlsplit


@contextmanager
def twitch_fixture():
    state = {
        "revoked": set(),
        "messages": [],
        "token_calls": 0,
        "pubsub_unavailable": False,
        "expired": set(),
        "access_users": {},
        "refresh_users": {},
        "refresh_calls": 0,
    }

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass  # Never write request headers, tokens or authorization codes.

        def reply(self, code, data):
            payload = json.dumps(data).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def do_GET(self):
            parsed = urlsplit(self.path)
            if parsed.path == "/oauth2/authorize":
                params = parse_qs(parsed.query)
                target = params.get("redirect_uri", [""])[0]
                destination = urlsplit(target)
                if destination.hostname not in {"localhost", "127.0.0.1"}:
                    return self.reply(400, {})
                self.send_response(302)
                self.send_header(
                    "Location",
                    target
                    + "?"
                    + urlencode({"code": "90001", "state": params.get("state", [""])[0]}),
                )
                self.end_headers()
                return
            if parsed.path == "/oauth2/validate":
                token = self.headers.get("Authorization", "").split(" ")[-1]
                if token == "fixture-app-token":
                    return self.reply(
                        200, {"client_id": "fixture-app", "user_id": None, "expires_in": 3600}
                    )
                if (
                    token in state["revoked"]
                    or "token-" + state["access_users"].get(token, token[6:]) in state["revoked"]
                    or token in state["expired"]
                    or not token.startswith("token-")
                ):
                    return self.reply(401, {})
                return self.reply(
                    200,
                    {
                        "client_id": "fixture-app",
                        "user_id": state["access_users"].get(token, token[6:]),
                        "expires_in": 3600,
                        "scopes": [],
                    },
                )
            if parsed.path == "/helix/streams":
                user = parse_qs(parsed.query)["user_id"][0]
                return self.reply(
                    200,
                    {
                        "data": [
                            {
                                "id": "fixture-stream-" + user,
                                "user_id": user,
                                "started_at": (
                                    datetime.now(UTC) - timedelta(minutes=5)
                                ).isoformat(),
                            }
                        ]
                    },
                )
            if parsed.path == "/helix/users":
                params = parse_qs(parsed.query)
                user = (
                    params["id"][0] if "id" in params else params["login"][0].removeprefix("user")
                )
                return self.reply(
                    200,
                    {
                        "data": [
                            {
                                "id": user,
                                "login": "user" + user,
                                "display_name": "Viewer" + user,
                                "profile_image_url": "https://example.test/avatar.png",
                            }
                        ]
                    },
                )
            return self.reply(404, {})

        def do_POST(self):
            payload = self.rfile.read(int(self.headers.get("Content-Length", "0")))
            if self.path == "/oauth2/token":
                data = parse_qs(payload.decode())
                if data.get("client_id") != ["fixture-app"]:
                    return self.reply(401, {})
                state["token_calls"] += 1
                if data.get("grant_type") == ["client_credentials"]:
                    return self.reply(
                        200, {"access_token": "fixture-app-token", "expires_in": 3600}
                    )
                if data.get("grant_type") == ["refresh_token"]:
                    old = data.get("refresh_token", [""])[0]
                    user = state["refresh_users"].pop(old, None)
                    if not user or "token-" + user in state["revoked"]:
                        return self.reply(400, {})
                    state["refresh_calls"] += 1
                    access = "token-" + user + "-r" + str(state["refresh_calls"])
                else:
                    user = data.get("code", ["90001"])[0]
                    access = "token-" + user
                refresh = "refresh-" + user + "-" + str(state["refresh_calls"]) + "%&"
                state["refresh_users"][refresh] = user
                state["access_users"][access] = user
                return self.reply(
                    200, {"access_token": access, "refresh_token": refresh, "expires_in": 3600}
                )
            if self.path == "/helix/extensions/pubsub":
                if state["pubsub_unavailable"]:
                    return self.reply(503, {})
                state["messages"].append(
                    {
                        "body": json.loads(payload),
                        "authorization": self.headers.get("Authorization"),
                        "client_id": self.headers.get("Client-Id"),
                    }
                )
                return self.reply(204, {})
            return self.reply(404, {})

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}", state
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
