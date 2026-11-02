"""Verified Twitch authentication with transactional backend-only HTTPS persistence."""

from cryptography.fernet import InvalidToken

from twitch_games.auth import Auth, Identity, csrf_token, digest
from twitch_games.errors import GameError
from twitch_games.http_game_service import actor


class HTTPAuth(Auth):
    def rpc(self, operation, **args):
        return self.require_database().rpc(operation, **args)

    def new_oauth_state(self, state):
        self.rpc("oauth_state_new", digest=digest(state))

    def consume_oauth_state(self, state):
        return self.rpc("oauth_state_consume", digest=digest(state))

    def store_login(self, user, access, refresh, seconds, session, old):
        self.rpc(
            "oauth_login",
            profile=user,
            access=self.cipher.encrypt(access.encode()).decode(),
            refresh=self.cipher.encrypt(refresh.encode()).decode(),
            seconds=seconds,
            session_digest=digest(session),
            old_digest=digest(old) if old else None,
        )

    def logout_session(self, session):
        self.rpc("logout", digest=digest(session))

    def check_http_authorization(self, user_id, force=False):
        packet = self.rpc("auth_claim", user_id=user_id, force=force)
        if packet["status"] == "valid":
            return True
        if packet["status"] == "revoked":
            return False
        record = packet["record"]
        lease = packet["lease"]

        def finish(**data):
            self.rpc("auth_finish", user_id=user_id, lease=lease, **data)

        try:
            access = self.cipher.decrypt(record["encrypted_access_token"].encode()).decode()
            refresh = (
                self.cipher.decrypt(record["encrypted_refresh_token"].encode()).decode()
                if record["encrypted_refresh_token"]
                else None
            )
            try:
                validated = self.provider.validate(access)
            except GameError as error:
                if error.status != 401:
                    raise
                if not refresh:
                    finish(revoke=True)
                    return False
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
                    finish(revoke=True)
                    return False
                refresh = tokens.get("refresh_token", refresh)
                if not isinstance(refresh, str) or not refresh:
                    raise GameError(
                        "twitch_unavailable", "Twitch returned an invalid refresh token", 503
                    ) from None
            if validated["user_id"] != user_id:
                finish(revoke=True)
                return False
            finish(
                access=self.cipher.encrypt(access.encode()).decode(),
                refresh=self.cipher.encrypt(refresh.encode()).decode() if refresh else None,
                seconds=validated["expires_in"],
            )
            return True
        except InvalidToken:
            finish(revoke=True)
            return False
        except GameError:
            try:
                finish()
            except GameError:
                pass
            raise

    def validate_session(self, session, force=False):
        if self.cipher is None or not self.settings.oauth_configured:
            raise GameError("not_configured", "Twitch OAuth configuration is required", 503)
        record = self.rpc("session_read", digest=digest(session))
        if not record:
            raise GameError("unauthenticated", "Log in with Twitch", 401)
        if not self.check_http_authorization(record["user_id"], force):
            raise GameError("unauthenticated", "Twitch authorization ended; sign in again", 401)
        return Identity(record["user_id"], record["user_id"], "broadcaster", "dashboard")

    def workspace(self, identity, channel):
        if identity.source != "dashboard" or identity.channel_id == channel:
            return identity
        candidate = Identity(channel, identity.user_id, "moderator", "dashboard")
        permissions = self.rpc("permissions", actor=actor(candidate))
        return Identity(channel, identity.user_id, "moderator", "dashboard", frozenset(permissions))

    def me(self, identity, channel, session=None):
        selected = self.workspace(identity, channel)
        result = self.rpc("identity", actor=actor(selected))
        result["csrf_token"] = csrf_token(session) if session else None
        return result

    def maintenance(self, startup=False):
        if not self.database or not self.settings.oauth_configured:
            return
        cursor = ""
        while not getattr(self, "stopping", False):
            users = self.rpc("auth_due", startup=startup, after=cursor)
            startup = False
            if not users:
                break
            for user in users:
                if getattr(self, "stopping", False):
                    return
                try:
                    self.check_http_authorization(user, True)
                except GameError as error:
                    if error.status != 503:
                        raise
            cursor = users[-1]
