"""Actual PostgREST plus a loopback test gateway translating a fake API key to JWT.

The gateway models Supabase's API-key authentication only; SQL/RPC execution is
handled by the official PostgREST process against disposable PostgreSQL.
"""

import json
import os
import secrets
import subprocess
import time
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread

import httpx2 as httpx
import jwt
import psycopg
from psycopg import sql
from sqlalchemy.engine import make_url

IMAGE = (
    "postgrest/postgrest@sha256:5f4ce744539bbba786b4e24dbbd95bdb2a956dcf568c5374995a0ff4a68f5bd2"
)
API_KEY = "sb_secret_local_http_test_only"


@contextmanager
def postgrest_fixture(dsn, container):
    password = secrets.token_urlsafe(24)
    jwt_secret = secrets.token_urlsafe(40)
    parsed = make_url(dsn)
    name = container + "-rest"
    started = False
    server = None
    with psycopg.connect(dsn) as c:
        c.execute(
            sql.SQL("CREATE ROLE authenticator LOGIN NOINHERIT PASSWORD {}").format(
                sql.Literal(password)
            )
        )
        c.execute("GRANT anon,authenticated,service_role TO authenticator")
    try:
        environment = {
            **os.environ,
            "PGRST_DB_URI": f"postgresql://authenticator:{password}@127.0.0.1:5432/{parsed.database}",
            "PGRST_JWT_SECRET": jwt_secret,
        }
        subprocess.run(
            [
                "docker",
                "run",
                "--detach",
                "--rm",
                "--name",
                name,
                "--network",
                "container:" + container,
                "--env",
                "PGRST_DB_URI",
                "--env",
                "PGRST_JWT_SECRET",
                "--env",
                "PGRST_DB_SCHEMAS=public",
                "--env",
                "PGRST_DB_ANON_ROLE=anon",
                "--env",
                "PGRST_LOG_LEVEL=crit",
                IMAGE,
            ],
            check=True,
            env=environment,
            stdout=subprocess.DEVNULL,
        )
        started = True
        port = (
            subprocess.check_output(["docker", "port", container, "3000"], text=True)
            .strip()
            .rsplit(":", 1)[1]
        )
        base = "http://127.0.0.1:" + port
        authorization = jwt.encode(
            {"role": "service_role", "exp": int(time.time()) + 3600}, jwt_secret, algorithm="HS256"
        )
        for _ in range(50):
            try:
                response = httpx.get(
                    base + "/", headers={"Authorization": "Bearer " + authorization}, timeout=2
                )
                if response.status_code == 200:
                    break
            except httpx.RequestError:
                pass
            time.sleep(0.2)
        else:
            raise RuntimeError("PostgREST did not become ready; no credentials logged")
        for role in ["anon", "authenticated"]:
            token = jwt.encode(
                {"role": role, "exp": int(time.time()) + 60}, jwt_secret, algorithm="HS256"
            )
            denied = httpx.post(
                base + "/rpc/twitch_games_backend",
                json={"operation": "health", "args": {}},
                headers={"Authorization": "Bearer " + token},
            )
            assert denied.status_code in {401, 403, 404}, (
                "Browser roles must not execute backend RPC"
            )
        print("Real PostgREST ready; anon/authenticated backend RPC access denied.", flush=True)

        reported_errors = set()
        startup_probe_failed = False

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def forward(self):
                nonlocal startup_probe_failed
                if self.headers.get("apikey") != API_KEY:
                    self.send_response(401)
                    self.end_headers()
                    return
                path = self.path.removeprefix("/rest/v1")
                body = self.rfile.read(int(self.headers.get("Content-Length", "0")))
                if body and not startup_probe_failed:
                    packet = json.loads(body)
                    if packet.get("operation") == "health":
                        startup_probe_failed = True
                        print(
                            "Injected one transient RPC startup failure (test fixture).", flush=True
                        )
                        self.send_response(503)
                        self.end_headers()
                        return
                with httpx.Client(timeout=10) as client:
                    response = client.request(
                        self.command,
                        base + path,
                        headers={
                            "Authorization": "Bearer " + authorization,
                            "Content-Type": "application/json",
                        },
                        content=body,
                    )
                if response.status_code >= 400:
                    error = response.json()
                    if (
                        error.get("code") in {"42702", "42703", "42883", "42P01", "42601"}
                        and error.get("message") not in reported_errors
                    ):
                        reported_errors.add(error.get("message"))
                        print(
                            "Test-only RPC SQL error:",
                            error["code"],
                            error.get("message"),
                            flush=True,
                        )
                self.send_response(response.status_code)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(response.content)))
                self.end_headers()
                self.wfile.write(response.content)

            do_GET = forward
            do_POST = forward

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        yield "http://127.0.0.1:" + str(server.server_port)
    finally:
        if server:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)
        if started:
            subprocess.run(
                ["docker", "rm", "--force", "--volumes", name],
                check=True,
                stdout=subprocess.DEVNULL,
            )
        print("Disposable PostgREST/gateway removed.", flush=True)
