"""Regression coverage for fail-closed hosted authentication configuration."""

import base64
import hashlib
import hmac
import json
import os
import unittest
from unittest.mock import patch

from app import issue_jwt_token, verify_token
from agent import get_vocal_hmac_secret


def _segment(value):
    return base64.urlsafe_b64encode(json.dumps(value, separators=(",", ":")).encode()).decode().rstrip("=")


class TestServerlessSecrets(unittest.TestCase):
    def test_public_vercel_values_cannot_mint_or_verify_tokens(self):
        commit_sha = "public-commit-sha-0123456789abcdef"
        with patch.dict(os.environ, {
            "VERCEL": "1",
            "VERCEL_ENV": "production",
            "VERCEL_URL": "riffs-agent.vercel.app",
            "VERCEL_REGION": "iad1",
            "VERCEL_GIT_COMMIT_SHA": commit_sha,
            "RIFFS_JWT_SECRET": "",
            "RIFFS_VOCAL_SECRET": "",
            "RIFFS_PUBLIC_DEMO": "",
            "RIFFS_ENABLE_DEMO_AUTH": "",
        }, clear=True):
            header = _segment({"alg": "HS256", "typ": "JWT"})
            claims = _segment({
                "sub": "attacker",
                "iss": "riffs-local-demo",
                "aud": "riffs-local-api",
                "exp": 4102444800,
                "roles": ["beta_tester"],
                "entitlements": ["generation"],
            })
            signed = f"{header}.{claims}".encode("ascii")
            public_derived_key = hashlib.sha256(commit_sha.encode("utf-8")).hexdigest().encode("utf-8")
            signature = base64.urlsafe_b64encode(hmac.new(public_derived_key, signed, hashlib.sha256).digest()).decode().rstrip("=")
            self.assertIsNone(verify_token(f"{header}.{claims}.{signature}"))
            with self.assertRaises(RuntimeError):
                issue_jwt_token()
            with self.assertRaises(RuntimeError):
                get_vocal_hmac_secret()


if __name__ == "__main__":
    unittest.main()
