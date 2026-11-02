import unittest

from fastapi.testclient import TestClient

from twitch_games.app import create_app
from twitch_games.auth import Principal, require_permission_admin
from twitch_games.contracts import Permission, PublicQuestion
from fastapi import HTTPException
from pydantic import ValidationError


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(create_app())

    def test_health_does_not_claim_ready(self):
        self.assertEqual(200, self.client.get("/health/live").status_code)
        self.assertEqual(503, self.client.get("/health/ready").status_code)

    def test_routes_fail_closed(self):
        for path in ["/channels/test/game-state", "/dashboard/channels/test"]:
            self.assertEqual(401, self.client.get(path).status_code)
            self.assertEqual(503, self.client.get(path, headers={"Authorization": "Bearer untrusted"}).status_code)

    def test_mod_cannot_grant_permissions(self):
        principal = Principal("mod", "channel", False, frozenset(Permission))
        with self.assertRaises(HTTPException) as error:
            require_permission_admin(principal, "channel")
        self.assertEqual(403, error.exception.status_code)

    def test_public_question_rejects_hidden_answer(self):
        with self.assertRaises(ValidationError):
            PublicQuestion(id="00000000-0000-0000-0000-000000000001", mode="niche", prompt="Prompt", position=1, total=3, canonical_answer="secret")


if __name__ == "__main__":
    unittest.main()
