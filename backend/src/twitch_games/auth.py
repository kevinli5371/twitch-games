"""Twitch OAuth sessions and strictly verified Extension identities."""

import base64
import hashlib
import hmac
import re
import secrets
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from threading import Lock
from urllib.parse import urlencode

import httpx2 as httpx
import jwt
from cryptography.fernet import Fernet, InvalidToken
from fastapi import APIRouter, Request, Response
from fastapi.responses import JSONResponse, RedirectResponse

from twitch_games.errors import GameError
from twitch_games.runtime_models import DashboardIdentity
from twitch_games.store import one, rows, run

SESSION_COOKIE = "twitch_games_session"
STATE_COOKIE = "twitch_games_oauth_state"
NUMERIC = re.compile(r"^[1-9][0-9]{0,31}$")


def digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def csrf_token(session: str) -> str:
    return hmac.new(session.encode(), b"twitch-games-csrf-v1", hashlib.sha256).hexdigest()


@dataclass(frozen=True)
class Identity:
    channel_id: str
    user_id: str | None
    role: str
    source: str = "extension"
    permissions: frozenset[str] = frozenset()

    def owner(self, channel_id):
        if self.role != "broadcaster" or self.channel_id != channel_id:
            raise GameError("forbidden", "Only this channel's broadcaster may do that", 403)

    def viewer(self, channel_id, participating=False):
        if self.channel_id != channel_id:
            raise GameError("forbidden", "Credential belongs to another channel", 403)
        if participating and not self.user_id:
            raise GameError("identity_required", "Share your Twitch identity to participate", 403)


class TwitchProvider:
    def __init__(self, settings):
        self.settings = settings
        test = settings.test_twitch_base_url
        self.oauth = (test + "/oauth2") if test else "https://id.twitch.tv/oauth2"
        self.helix = (test + "/helix") if test else "https://api.twitch.tv/helix"
        self.client = httpx.Client(timeout=5, follow_redirects=False)
        self.app_token_lock = Lock()
        self.app_token = None
        self.app_token_until = 0

    def call(self, method, url, auth_errors=False, **kwargs):
        try:
            response = self.client.request(method, url, **kwargs)
            if response.status_code == 401 or (auth_errors and response.status_code == 400):
                raise GameError("unauthenticated", "Twitch authorization is no longer valid", 401)
            if response.status_code >= 300:
                raise GameError("twitch_unavailable", "Twitch request failed; retry shortly", 503)
            return response.json() if response.content else {}
        except (httpx.HTTPError, ValueError):
            raise GameError(
                "twitch_unavailable", "Twitch is temporarily unavailable", 503
            ) from None

    def token(self, **data):
        s = self.settings
        if not s.twitch_client_id or not s.twitch_client_secret:
            raise GameError("not_configured", "Twitch OAuth configuration is required", 503)
        return self.call(
            "POST",
            self.oauth + "/token",
            auth_errors=True,
            data={
                "client_id": s.twitch_client_id,
                "client_secret": s.twitch_client_secret.get_secret_value(),
                **data,
            },
        )

    def validate(self, token):
        data = self.call(
            "GET", self.oauth + "/validate", headers={"Authorization": "OAuth " + token}
        )
        if (
            data.get("client_id") != self.settings.twitch_client_id
            or not NUMERIC.fullmatch(str(data.get("user_id", "")))
            or not isinstance(data.get("expires_in"), int)
            or data["expires_in"] <= 0
        ):
            raise GameError("unauthenticated", "Twitch token identity is invalid", 401)
        return data

    def app_access(self):
        with self.app_token_lock:
            if time.monotonic() >= self.app_token_until:
                data = self.token(grant_type="client_credentials")
                self.app_token = data["access_token"]
                validated = self.call(
                    "GET",
                    self.oauth + "/validate",
                    headers={"Authorization": "OAuth " + self.app_token},
                )
                if validated.get("client_id") != self.settings.twitch_client_id:
                    raise GameError("unauthenticated", "Application token client mismatch", 401)
                self.app_token_until = time.monotonic() + max(0, min(data["expires_in"] - 60, 3600))
        return self.app_token

    def user_by_login(self, login):
        data = self.call(
            "GET",
            self.helix + "/users",
            params={"login": login},
            headers={
                "Authorization": "Bearer " + self.app_access(),
                "Client-Id": self.settings.twitch_client_id,
            },
        )
        users = data.get("data", [])
        if len(users) != 1 or users[0].get("login", "").casefold() != login.casefold():
            raise GameError("not_found", "Twitch user was not found", 404)
        if not NUMERIC.fullmatch(users[0].get("id", "")):
            raise GameError("twitch_unavailable", "Twitch returned an invalid identity", 503)
        return users[0]

    def user(self, user_id, token=None):
        token = token if token is not None else self.app_access()
        try:
            data = self.call(
                "GET",
                self.helix + "/users",
                params={"id": user_id},
                headers={
                    "Authorization": "Bearer " + token,
                    "Client-Id": self.settings.twitch_client_id,
                },
            )
        except GameError as error:
            if error.status == 401:
                self.app_token_until = 0
            raise
        users = data.get("data", [])
        if len(users) != 1 or users[0].get("id") != user_id:
            raise GameError("unauthenticated", "Twitch user could not be verified", 401)
        return users[0]


class Auth:
    def __init__(self, settings, database):
        self.settings, self.database = settings, database
        self.provider = TwitchProvider(settings)
        self.cipher = (
            Fernet(settings.token_encryption_key.get_secret_value().encode())
            if settings.token_encryption_key
            else None
        )
        self.extension_key = (
            base64.b64decode(settings.twitch_extension_secret.get_secret_value())
            if settings.twitch_extension_secret
            else None
        )

    def require_database(self):
        if self.database is None:
            raise GameError("not_configured", "Database configuration is required", 503)
        return self.database

    def extension(self, token):
        if not self.settings.extension_configured:
            raise GameError("not_configured", "Twitch Extension configuration is required", 503)
        try:
            data = jwt.decode(
                token,
                self.extension_key,
                algorithms=["HS256"],
                options={
                    "require": ["exp", "channel_id", "role", "opaque_user_id"],
                    "verify_aud": False,
                },
            )
            channel = data["channel_id"]
            user = data.get("user_id")
            if (
                not isinstance(channel, str)
                or not NUMERIC.fullmatch(channel)
                or data["role"] not in {"viewer", "moderator", "broadcaster"}
                or not isinstance(data["opaque_user_id"], str)
                or (user is not None and (not isinstance(user, str) or not NUMERIC.fullmatch(user)))
                or (
                    user is not None
                    and (
                        not data["opaque_user_id"].startswith("U")
                        or data.get("is_unlinked") is True
                    )
                )
                or (data["role"] == "broadcaster" and user is not None and user != channel)
            ):
                raise ValueError
            return Identity(channel, user, data["role"])
        except (jwt.PyJWTError, ValueError, TypeError):
            raise GameError("unauthenticated", "Invalid or expired Extension token", 401) from None

    def save_profile(self, c, user):
        run(
            c,
            "INSERT INTO twitch_games.twitch_users(id,login,display_name,profile_image_url) "
            "VALUES (:id,:login,:name,:image) ON CONFLICT(id) DO UPDATE SET "
            "login=excluded.login,display_name=excluded.display_name,"
            "profile_image_url=excluded.profile_image_url,updated_at=now()",
            id=user["id"],
            login=user.get("login"),
            name=user["display_name"],
            image=user.get("profile_image_url"),
        )

    def revoke(self, c, user_id):
        run(
            c,
            "UPDATE twitch_games.oauth_authorizations SET revoked_at=clock_timestamp() "
            "WHERE user_id=:id",
            id=user_id,
        )
        run(c, "DELETE FROM twitch_games.dashboard_sessions WHERE user_id=:id", id=user_id)

    def check_authorization(self, c, user_id, force=False):
        record = one(
            c,
            "SELECT * FROM twitch_games.oauth_authorizations WHERE user_id=:id FOR UPDATE",
            id=user_id,
        )
        if not record or record["revoked_at"] is not None:
            return False
        now = datetime.now(UTC)
        if (
            not force
            and record["access_expires_at"] > now
            and (now - record["validated_at"]).total_seconds() < 3600
        ):
            return True
        try:
            access = self.cipher.decrypt(record["encrypted_access_token"].encode()).decode()
            try:
                validated = self.provider.validate(access)
            except GameError as error:
                if error.status != 401:
                    raise
                if not record["encrypted_refresh_token"]:
                    self.revoke(c, user_id)
                    return False
                refresh = self.cipher.decrypt(record["encrypted_refresh_token"].encode()).decode()
                try:
                    tokens = self.provider.token(grant_type="refresh_token", refresh_token=refresh)
                    access = tokens.get("access_token")
                    if not isinstance(access, str) or not access:
                        raise GameError(
                            "twitch_unavailable", "Twitch returned an invalid refresh response", 503
                        )
                    validated = self.provider.validate(access)
                except GameError as refresh_error:
                    if refresh_error.status != 401:
                        raise
                    self.revoke(c, user_id)
                    return False
                replacement = tokens.get("refresh_token", refresh)
                if not isinstance(replacement, str) or not replacement:
                    raise GameError(
                        "twitch_unavailable", "Twitch returned an invalid refresh token", 503
                    ) from None
                run(
                    c,
                    "UPDATE twitch_games.oauth_authorizations SET encrypted_access_token=:access,"
                    "encrypted_refresh_token=:refresh WHERE user_id=:id",
                    id=user_id,
                    access=self.cipher.encrypt(access.encode()).decode(),
                    refresh=self.cipher.encrypt(replacement.encode()).decode(),
                )
            if validated["user_id"] != user_id:
                self.revoke(c, user_id)
                return False
        except InvalidToken:
            self.revoke(c, user_id)
            return False
        run(
            c,
            "UPDATE twitch_games.oauth_authorizations SET validated_at=clock_timestamp(),"
            "access_expires_at=clock_timestamp()+make_interval(secs=>:seconds) WHERE user_id=:id",
            id=user_id,
            seconds=validated["expires_in"],
        )
        return True

    def validate_session(self, session, force=False):
        if self.cipher is None or not self.settings.oauth_configured:
            raise GameError("not_configured", "Twitch OAuth configuration is required", 503)
        with self.require_database().transaction() as c:
            record = one(
                c,
                "SELECT * FROM twitch_games.dashboard_sessions WHERE digest=:digest "
                "AND expires_at>clock_timestamp()",
                digest=digest(session),
            )
            if not record:
                raise GameError("unauthenticated", "Log in with Twitch", 401)
            valid = self.check_authorization(c, record["user_id"], force)
        if not valid:
            raise GameError("unauthenticated", "Twitch authorization ended; sign in again", 401)
        return Identity(record["user_id"], record["user_id"], "broadcaster", "dashboard")

    def identity(self, request, authorization=None):
        header = (
            authorization if authorization is not None else request.headers.get("Authorization")
        )
        if header is not None:
            if not header.startswith("Bearer ") or len(header) > 8192:
                raise GameError("unauthenticated", "Use a Twitch Extension Bearer token", 401)
            return self.extension(header[7:])
        session = request.cookies.get(SESSION_COOKIE)
        if not session or len(session) > 128:
            raise GameError("unauthenticated", "A Twitch credential is required", 401)
        identity = self.validate_session(session)
        if request.method not in {"GET", "HEAD", "OPTIONS"}:
            if not hmac.compare_digest(
                csrf_token(session), request.headers.get("X-CSRF-Token", "")
            ):
                raise GameError("forbidden", "Missing or invalid CSRF token", 403)
        return identity

    def effective_permissions(self, c, identity, channel):
        if identity.channel_id != channel:
            raise GameError("forbidden", "Credential belongs to another channel", 403)
        if identity.role == "broadcaster" and (identity.user_id in {None, channel}):
            return frozenset({"question_review", "live_control", "settings"})
        if not identity.user_id:
            return frozenset()
        return frozenset(
            r["permission"]
            for r in rows(
                c,
                "SELECT permission FROM twitch_games.moderator_grants WHERE channel_id=:channel "
                "AND moderator_twitch_id=:user",
                channel=channel,
                user=identity.user_id,
            )
        )

    def require_permission(self, c, identity, channel, permission=None):
        permissions = self.effective_permissions(c, identity, channel)
        if not permissions or (permission is not None and permission not in permissions):
            raise GameError("forbidden", "This workspace permission has not been granted", 403)
        return permissions

    def workspace(self, identity, channel):
        if identity.source != "dashboard" or identity.channel_id == channel:
            return identity
        candidate = Identity(channel, identity.user_id, "moderator", "dashboard")
        with self.require_database().transaction() as c:
            permissions = self.require_permission(c, candidate, channel)
        return Identity(channel, identity.user_id, "moderator", "dashboard", permissions)

    def me(self, identity, channel, session=None):
        selected = self.workspace(identity, channel)
        with self.require_database().transaction() as c:
            permissions = self.require_permission(c, selected, channel)
            profile = one(
                c,
                "SELECT id AS user_id,login,display_name,profile_image_url AS avatar_url "
                "FROM twitch_games.twitch_users WHERE id=:id",
                id=identity.user_id,
            )
            own = one(
                c,
                "SELECT id AS channel_id,display_name FROM twitch_games.channels WHERE id=:id",
                id=identity.user_id,
            )
            granted = rows(
                c,
                "SELECT g.channel_id,c.display_name,array_agg(g.permission ORDER BY g.permission) "
                "AS permissions FROM twitch_games.moderator_grants g "
                "JOIN twitch_games.channels c ON c.id=g.channel_id WHERE moderator_twitch_id=:id "
                "GROUP BY g.channel_id,c.display_name ORDER BY g.channel_id",
                id=identity.user_id,
            )
            workspaces = [
                {
                    "channel_id": identity.user_id,
                    "display_name": own["display_name"] if own else None,
                    "role": "owner",
                    "permissions": ["live_control", "question_review", "settings"],
                }
            ]
            workspaces.extend({**dict(row), "role": "moderator"} for row in granted)
            return {
                "user": dict(profile) if profile else None,
                "owned_channel": dict(own) if own else None,
                "workspaces": workspaces,
                "selected_workspace": {
                    "channel_id": channel,
                    "role": "owner" if selected.role == "broadcaster" else "moderator",
                    "permissions": sorted(permissions),
                },
                "csrf_token": csrf_token(session) if session else None,
            }

    def maintenance(self, startup=False):
        if not self.database or not self.settings.oauth_configured:
            return
        with self.database.transaction() as c:
            run(c, "DELETE FROM twitch_games.oauth_states WHERE expires_at<=now()")
            run(c, "DELETE FROM twitch_games.dashboard_sessions WHERE expires_at<=now()")
            if startup:
                run(
                    c,
                    "UPDATE twitch_games.oauth_authorizations SET validated_at='epoch' WHERE "
                    "revoked_at IS NULL",
                )
        cursor = ""
        while not getattr(self, "stopping", False):
            with self.database.transaction() as c:
                due = rows(
                    c,
                    "SELECT user_id FROM twitch_games.oauth_authorizations WHERE user_id>:cursor "
                    "AND revoked_at IS NULL AND (validated_at<=now()-interval '1 hour' OR "
                    "access_expires_at<=now()) "
                    "ORDER BY user_id LIMIT 100",
                    cursor=cursor,
                )
            if not due:
                break
            for record in due:
                if getattr(self, "stopping", False):
                    return
                try:
                    with self.database.transaction() as c:
                        self.check_authorization(c, record["user_id"], force=True)
                except GameError as error:
                    if error.status != 503:
                        raise
            cursor = due[-1]["user_id"]


router = APIRouter(prefix="/api/v1/auth", tags=["authentication"])


@router.get("/twitch", status_code=302, response_class=RedirectResponse)
def login(request: Request):
    auth = request.app.state.auth
    if not auth.settings.oauth_configured:
        raise GameError("not_configured", "Configure Twitch OAuth before logging in", 503)
    state = secrets.token_urlsafe(32)
    with auth.require_database().transaction() as c:
        run(
            c,
            "INSERT INTO twitch_games.oauth_states(digest,expires_at) "
            "VALUES (:digest,now()+interval '10 minutes')",
            digest=digest(state),
        )
    response = RedirectResponse(
        auth.provider.oauth
        + "/authorize?"
        + urlencode(
            {
                "client_id": auth.settings.twitch_client_id,
                "redirect_uri": auth.settings.twitch_redirect_uri,
                "response_type": "code",
                "scope": "",
                "state": state,
            }
        ),
        status_code=302,
    )
    response.set_cookie(
        STATE_COOKIE,
        state,
        max_age=600,
        httponly=True,
        samesite="lax",
        secure=auth.settings.environment == "production",
    )
    return response


@router.get(
    "/twitch/callback", responses={303: {"description": "Return to the configured dashboard"}}
)
def callback(request: Request, state: str = "", code: str = "", error: str | None = None):
    auth = request.app.state.auth
    expected = request.cookies.get(STATE_COOKIE, "")
    if not state or len(state) > 128 or not hmac.compare_digest(state, expected):
        raise GameError("unauthenticated", "OAuth state is invalid", 401)
    if not auth.settings.oauth_configured:
        raise GameError("not_configured", "Configure Twitch OAuth before logging in", 503)
    with auth.require_database().transaction() as c:
        record = one(
            c,
            "DELETE FROM twitch_games.oauth_states WHERE digest=:digest "
            "AND expires_at>now() RETURNING digest",
            digest=digest(state),
        )
    if record is None:
        raise GameError("unauthenticated", "OAuth state expired or was already used", 401)
    if error or not code or len(code) > 2048:
        raise GameError("consent_denied", "Twitch sign-in was denied or cancelled", 401)
    tokens = auth.provider.token(
        grant_type="authorization_code", code=code, redirect_uri=auth.settings.twitch_redirect_uri
    )
    access, refresh = tokens.get("access_token"), tokens.get("refresh_token")
    if not isinstance(access, str) or not isinstance(refresh, str) or not access or not refresh:
        raise GameError(
            "twitch_unavailable", "Twitch returned incomplete authorization tokens", 503
        )
    verified = auth.provider.validate(access)
    user = auth.provider.user(verified["user_id"], access)
    session = secrets.token_urlsafe(32)
    with auth.database.transaction() as c:
        auth.save_profile(c, user)
        run(
            c,
            "INSERT INTO twitch_games.channels(id,display_name) VALUES (:id,:name) "
            "ON CONFLICT(id) DO UPDATE SET display_name=excluded.display_name",
            id=user["id"],
            name=user["display_name"],
        )
        run(
            c,
            "INSERT INTO twitch_games.oauth_authorizations "
            "(user_id,encrypted_access_token,encrypted_refresh_token,access_expires_at,"
            "validated_at) "
            "VALUES (:id,:access,:refresh,"
            "clock_timestamp()+make_interval(secs=>:seconds),clock_timestamp()) "
            "ON CONFLICT(user_id) DO UPDATE SET "
            "encrypted_access_token=excluded.encrypted_access_token,"
            "encrypted_refresh_token=excluded.encrypted_refresh_token,"
            "access_expires_at=excluded.access_expires_at,"
            "validated_at=excluded.validated_at,revoked_at=NULL",
            id=user["id"],
            access=auth.cipher.encrypt(access.encode()).decode(),
            refresh=auth.cipher.encrypt(refresh.encode()).decode(),
            seconds=verified["expires_in"],
        )
        old = request.cookies.get(SESSION_COOKIE)
        if old:
            run(
                c,
                "DELETE FROM twitch_games.dashboard_sessions WHERE digest=:digest",
                digest=digest(old),
            )
        run(
            c,
            "INSERT INTO twitch_games.dashboard_sessions(digest,user_id,expires_at) "
            "VALUES (:digest,:id,clock_timestamp()+interval '24 hours')",
            digest=digest(session),
            id=user["id"],
        )
    response = (
        RedirectResponse(auth.settings.dashboard_url, status_code=303)
        if auth.settings.dashboard_url
        else JSONResponse({"channel_id": user["id"], "status": "authenticated"})
    )
    response.delete_cookie(STATE_COOKIE)
    response.set_cookie(
        SESSION_COOKIE,
        session,
        max_age=86400,
        httponly=True,
        samesite="lax",
        secure=auth.settings.environment == "production",
    )
    return response


@router.get("/me", response_model=DashboardIdentity)
def me(request: Request, channel_id: str | None = None):
    auth = request.app.state.auth
    identity = auth.identity(request)
    if identity.source != "dashboard":
        raise GameError("unauthenticated", "Dashboard session cookie is required", 401)
    return auth.me(identity, channel_id or identity.user_id, request.cookies.get(SESSION_COOKIE))


@router.get("/session", deprecated=True)
def session_info(request: Request):
    auth = request.app.state.auth
    identity = auth.identity(request)
    session = request.cookies.get(SESSION_COOKIE)
    return {
        "channel_id": identity.channel_id,
        "user_id": identity.user_id,
        "role": identity.role,
        "csrf_token": csrf_token(session) if session and identity.source == "dashboard" else None,
    }


@router.post("/logout", status_code=204)
def logout(request: Request):
    auth = request.app.state.auth
    auth.identity(request)
    session = request.cookies.get(SESSION_COOKIE)
    if session:
        with auth.require_database().transaction() as c:
            run(
                c,
                "DELETE FROM twitch_games.dashboard_sessions WHERE digest=:digest",
                digest=digest(session),
            )
    response = Response(status_code=204)
    response.delete_cookie(SESSION_COOKIE)
    return response
