"""Regression coverage for the human-reviewed vocal lane and approval boundary."""

import copy
import base64
import hashlib
import hmac
import json
import os
import sys
import time
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent import RiffsAgent
from riffs_api.prompt_guardrails import PromptRefusal, validate_prompt
from riffs_api.vocal_approval import (
    VocalApprovalUnavailable,
    VocalInputError,
    consume_vocal_token,
    issue_vocal_token,
    normalize_lyrics,
)


class _MemoryRedis:
    def __init__(self):
        self.values = set()

    def set(self, key, value, *, ex, nx):
        if nx and key in self.values:
            return None
        self.values.add(key)
        return True


class TestLyricsVocalHITL(unittest.TestCase):
    def setUp(self):
        self.secret_patch = patch.dict(os.environ, {
            "RIFFS_VOCAL_SECRET": "test-only-secret-that-is-long-enough-32",
            "ANTHROPIC_API_KEY": "",
        })
        self.secret_patch.start()
        self.redis_patch = patch("riffs_api.storage.get_redis", return_value=_MemoryRedis())
        self.redis_patch.start()
        self.agent = RiffsAgent()
        self.agent.api_key = None

    def tearDown(self):
        self.redis_patch.stop()
        self.secret_patch.stop()

    def _request(self, *, chords="Am - F - C - G", **overrides):
        request = {
            "prompt": "Original soul loop",
            "key": "Am",
            "bpm": 110,
            "chords": chords,
            "instruments": ["bass_guitar", "rhythm_guitar", "cymbals"],
            "seed": 17,
            "groove": "straight",
            "lyrics_prompt": "Rain on the windowpane",
            "lyrics_language": "en",
            "vocal_style": "soulful_lead",
        }
        request.update(overrides)
        return request

    def _checkpoint(self, **kwargs):
        return self.agent.generate(**self._request(**kwargs))

    def _approve(self, checkpoint, *, edited=None, **kwargs):
        request = self._request(**kwargs)
        reviewed_lyrics = edited if edited is not None else checkpoint["lyrics_draft"]["bars"]
        result = self.agent.generate(
            **request,
            vocal_approved=True,
            vocal_approval_token=checkpoint["vocal_confirmation_token"],
            lyrics_draft=checkpoint["lyrics_draft"]["bars"],
            edited_lyrics=reviewed_lyrics,
            vocal_trace_id=checkpoint["vocal_trace_id"],
            acknowledge_unassessed_rights=True,
        )
        if result["status"] == "awaiting_vocal_confirmation":
            result = self.agent.generate(
                **request,
                vocal_approved=True,
                vocal_approval_token=result["vocal_confirmation_token"],
                lyrics_draft=result["lyrics_draft"]["bars"],
                edited_lyrics=result["lyrics_draft"]["bars"],
                vocal_trace_id=result["vocal_trace_id"],
                acknowledge_unassessed_rights=True,
            )
        return result

    def test_checkpoint_has_no_vocal_lane_and_returns_trace_id(self):
        result = self._checkpoint()
        self.assertEqual(result["status"], "awaiting_vocal_confirmation")
        self.assertTrue(result["vocal_trace_id"])
        self.assertNotIn("take_id", result)
        self.assertFalse(any(stem["lane"] == "vocal_lead" for stem in result["stems"]))
        self.assertNotIn(result["vocal_confirmation_token"], str(self.agent.take_history))

    def test_token_binds_full_context_and_exact_draft(self):
        context = {"trace_id": "trace-a", "prompt": "one", "groove": "straight"}
        lyrics = [{"bar": 1, "chord": "Am", "text": "first draft"}]
        token = issue_vocal_token(context, lyrics)
        self.assertFalse(consume_vocal_token(token, {**context, "groove": "half_time"}, lyrics))
        self.assertFalse(consume_vocal_token(token, context, [{**lyrics[0], "text": "edited"}]))
        self.assertTrue(consume_vocal_token(token, context, lyrics))
        self.assertFalse(consume_vocal_token(token, context, lyrics))

    def test_vocal_replay_storage_failure_fails_closed(self):
        context = {"trace_id": "redis-unavailable"}
        lyrics = [{"bar": 1, "chord": "Am", "text": "line"}]
        token = issue_vocal_token(context, lyrics)
        with patch("riffs_api.storage.get_redis", side_effect=ConnectionError("offline")):
            with self.assertRaises(VocalApprovalUnavailable):
                consume_vocal_token(token, context, lyrics)

    def test_token_expires(self):
        context = {"trace_id": "expired"}
        lyrics = [{"bar": 1, "chord": "Am", "text": "line"}]
        with patch("riffs_api.vocal_approval.time.time", return_value=1000):
            token = issue_vocal_token(context, lyrics)
        with patch("riffs_api.vocal_approval.time.time", return_value=1601):
            self.assertFalse(consume_vocal_token(token, context, lyrics))

    def test_trace_logs_are_correlated_and_redacted(self):
        context = {"trace_id": "trace-redacted", "prompt": "private prompt"}
        lyrics = [{"bar": 1, "chord": "Am", "text": "private lyric text"}]
        with self.assertLogs("riffs.vocal_approval", level="INFO") as captured:
            token = issue_vocal_token(context, lyrics)
            self.assertTrue(consume_vocal_token(token, context, lyrics))
        log_text = "\\n".join(captured.output)
        self.assertIn("trace-redacted", log_text)
        self.assertIn("checkpoint_issued", log_text)
        self.assertIn("approval_accepted", log_text)
        self.assertIn("draft_sha256", log_text)
        self.assertNotIn("private lyric text", log_text)
        self.assertNotIn(token, log_text)

    def test_missing_secret_disables_vocal_approval_without_revealing_config(self):
        with patch.dict(os.environ, {"RIFFS_VOCAL_SECRET": ""}):
            with self.assertRaisesRegex(VocalApprovalUnavailable, "unavailable"):
                issue_vocal_token({"trace_id": "no-secret"}, [{"bar": 1, "chord": "Am", "text": "line"}])

    def test_edited_draft_requires_a_second_confirmation(self):
        checkpoint = self._checkpoint()
        edited = copy.deepcopy(checkpoint["lyrics_draft"]["bars"])
        edited[0]["text"] = "A changed line under moonlight"
        request = self._request()
        first_approval = self.agent.generate(
            **request,
            vocal_approved=True,
            vocal_approval_token=checkpoint["vocal_confirmation_token"],
            lyrics_draft=checkpoint["lyrics_draft"]["bars"],
            edited_lyrics=edited,
            vocal_trace_id=checkpoint["vocal_trace_id"],
            acknowledge_unassessed_rights=True,
        )
        self.assertEqual(first_approval["status"], "awaiting_vocal_confirmation")
        self.assertFalse(any(stem["lane"] == "vocal_lead" for stem in first_approval["stems"]))
        approved = self.agent.generate(
            **request,
            vocal_approved=True,
            vocal_approval_token=first_approval["vocal_confirmation_token"],
            lyrics_draft=first_approval["lyrics_draft"]["bars"],
            edited_lyrics=first_approval["lyrics_draft"]["bars"],
            vocal_trace_id=first_approval["vocal_trace_id"],
            acknowledge_unassessed_rights=True,
        )
        self.assertEqual(approved["status"], "success")
        self.assertEqual(approved["lyrics"][0]["text"], edited[0]["text"])

    def test_malformed_or_unsafe_edited_lyrics_are_rejected(self):
        chords = ["Am", "F"]
        for bad in ([], ["" , "ok"], [None, "ok"], [{"text": None}, {"lyric": 123}], ["<script>alert(1)</script>", "ok"], ["kill them all", "ok"], ["x" * 181, "ok"]):
            with self.subTest(bad=bad):
                with self.assertRaises(VocalInputError):
                    normalize_lyrics(bad, chords)

    def test_exact_named_lyrics_request_is_refused(self):
        with self.assertRaises(PromptRefusal) as caught:
            validate_prompt("write the exact lyrics of Bohemian Rhapsody verbatim", allow_lyrics=True)
        self.assertEqual(caught.exception.code, "COPYRIGHT_REPRODUCTION_REQUEST")

    def test_vocal_bars_and_midi_metadata_follow_progression_length(self):
        for progression in ("Am - F", "Am - F - C - G - Dm - Em - F - G"):
            with self.subTest(progression=progression):
                checkpoint = self._checkpoint(chords=progression)
                self.assertEqual(len(checkpoint["lyrics_draft"]["bars"]), len(progression.split(" - ")))
                approved = self._approve(checkpoint, chords=progression)
                self.assertEqual(approved["status"], "success")
                self.assertIn("vocal_lead", approved["part_scores"])
                vocal_part = approved["part_scores"]["vocal_lead"]
                self.assertTrue(vocal_part["midi_sha256"])
                stem = next(s for s in approved["stems"] if s["lane"] == "vocal_lead")
                self.assertEqual(stem["midi_sha256"], vocal_part["midi_sha256"])
                self.assertEqual(len(vocal_part["bars"]), len(progression.split(" - ")))

    def test_vocal_lane_lock_reuses_prior_events(self):
        first_checkpoint = self._checkpoint()
        first = self._approve(first_checkpoint)
        first_lane = next(lane for lane in first["score"]["lanes"] if lane["instrument"] == "vocal_lead")
        request = self._request(locked_parts=["vocal_lead"], previous_score=first["score"], seed=18)
        checkpoint = self.agent.generate(**request)
        approved = self.agent.generate(
            **request,
            vocal_approved=True,
            vocal_approval_token=checkpoint["vocal_confirmation_token"],
            lyrics_draft=checkpoint["lyrics_draft"]["bars"],
            edited_lyrics=checkpoint["lyrics_draft"]["bars"],
            vocal_trace_id=checkpoint["vocal_trace_id"],
            acknowledge_unassessed_rights=True,
        )
        next_lane = next(lane for lane in approved["score"]["lanes"] if lane["instrument"] == "vocal_lead")
        self.assertTrue(next_lane["locked"])
        self.assertEqual(next_lane["hash"], first_lane["hash"])

    def test_api_preserves_structured_refusal_code(self):
        try:
            from fastapi.testclient import TestClient
            from app import app
            client = TestClient(app)
        except ImportError as exc:
            self.skipTest(f"API test dependencies are not installed here: {exc}")
        claims = {"sub": "test-user", "roles": ["beta_tester"], "entitlements": ["generation"]}
        with patch("app.verify_token", return_value=claims), patch("app.increment_generation_count", return_value=1):
            response = client.post(
                "/api/generate",
                json={"prompt": "Write lyrics about love"},
                headers={"Authorization": "Bearer test-token"},
            )
        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()["code"], "INSTRUMENTAL_ONLY")
        self.assertIn("alternative", response.json())

    def test_generate_rejects_legacy_license_flag(self):
        try:
            from fastapi.testclient import TestClient
            from app import app
            from unittest.mock import patch
            client = TestClient(app)
        except ImportError as exc:
            self.skipTest(f"API test dependencies are not installed here: {exc}")

        agent = RiffsAgent()
        agent.api_key = None
        claims = {"sub": "test-user", "roles": ["beta_tester"], "entitlements": ["generation"]}
        with patch("app.RiffsAgent", return_value=agent), \
                patch("app.verify_token", return_value=claims), \
                patch("app.increment_generation_count", return_value=1):
            response = client.post(
                "/api/generate",
                json={"prompt": "x", "issue_license": True},
                headers={"Authorization": "Bearer test-token"},
            )

        self.assertEqual(response.status_code, 422)

    def test_generate_never_issues_license(self):
        from fastapi.testclient import TestClient
        from app import app

        agent = RiffsAgent()
        agent.api_key = None
        claims = {"sub": "test-user", "roles": ["beta_tester"], "entitlements": ["generation"]}
        with patch("app.RiffsAgent", return_value=agent), \
                patch("app.verify_token", return_value=claims), \
                patch("app.increment_generation_count", return_value=1):
            response = TestClient(app).post(
                "/api/generate",
                json={"prompt": "x"},
                headers={"Authorization": "Bearer test-token"},
            )

        self.assertEqual(response.status_code, 200)
        payload = response.json()["data"]
        self.assertEqual(payload["license_certificate"]["status"], "not_issued")
        self.assertIsNone(payload["license_certificate"]["license_id"])

    def test_generate_requires_auth(self):
        from fastapi.testclient import TestClient
        from app import app

        response = TestClient(app).post("/api/generate", json={"prompt": "x"})
        self.assertEqual(response.status_code, 401)

    def test_generate_requires_entitlement(self):
        from fastapi.testclient import TestClient
        from app import app

        claims = {"sub": "test-user", "roles": ["beta_tester"], "entitlements": []}
        with patch("app.verify_token", return_value=claims):
            response = TestClient(app).post(
                "/api/generate",
                json={"prompt": "x"},
                headers={"Authorization": "Bearer no-generation-entitlement"},
            )
        self.assertEqual(response.status_code, 403)

    def test_generate_rate_limited(self):
        from fastapi.testclient import TestClient
        from app import app

        client = TestClient(app)
        headers = {"Authorization": "Bearer authorized-beta-tester"}
        claims = {"sub": "test-user", "roles": ["beta_tester"], "entitlements": ["generation"]}
        counts = {}

        def increment(user, now):
            counts[user] = counts.get(user, 0) + 1
            return counts[user]

        with patch("app.verify_token", return_value=claims), patch("app.increment_generation_count", side_effect=increment):
            statuses = [
                client.post("/api/generate", json={"prompt": "x"}, headers=headers).status_code
                for _ in range(11)
            ]
        self.assertEqual(statuses[-1], 429)

    def test_generation_rate_counter_uses_shared_redis_window(self):
        from app import increment_generation_count
        from unittest.mock import Mock

        redis_client = Mock()
        redis_client.eval.return_value = 4
        with patch("riffs_api.storage.get_redis", return_value=redis_client):
            count = increment_generation_count("user-1", now=120)

        self.assertEqual(count, 4)
        args = redis_client.eval.call_args.args
        self.assertEqual(args[1], 1)
        self.assertEqual(args[2], f"rl:generation:{hashlib.sha256(b'user-1').hexdigest()[:32]}:2")
        self.assertEqual(args[3], 60)

    def test_vocal_approval_requires_auth(self):
        from fastapi.testclient import TestClient
        from app import app

        response = TestClient(app).post(
            "/api/vocals/approve",
            json={"token": "unused", "lyrics_prompt": "A hopeful line"},
        )
        self.assertEqual(response.status_code, 401)

    def test_verify_token_checks_signature_issuer_audience_and_expiry(self):
        from app import verify_token

        secret = "test-signing-secret-with-32-bytes!!"
        header = {"alg": "HS256", "typ": "JWT"}
        claims = {
            "sub": "test-user",
            "iss": "test-issuer",
            "aud": "test-audience",
            "exp": time.time() + 60,
            "roles": ["beta_tester"],
            "entitlements": ["generation"],
        }

        def encode(value):
            return base64.urlsafe_b64encode(json.dumps(value, separators=(",", ":")).encode()).decode().rstrip("=")

        header_segment = encode(header)
        claims_segment = encode(claims)
        signed = f"{header_segment}.{claims_segment}".encode("ascii")
        signature = base64.urlsafe_b64encode(hmac.new(secret.encode(), signed, hashlib.sha256).digest()).decode().rstrip("=")
        token = f"{header_segment}.{claims_segment}.{signature}"

        config = {
            "RIFFS_JWT_SECRET": secret,
            "RIFFS_JWT_ISSUER": "test-issuer",
            "RIFFS_JWT_AUDIENCE": "test-audience",
        }
        with patch.dict(os.environ, config):
            self.assertEqual(verify_token(token), claims)
            self.assertIsNone(verify_token(f"{header_segment}.{claims_segment}.invalid"))

        expired_claims = {**claims, "exp": time.time() - 1}
        expired_segment = encode(expired_claims)
        expired_signed = f"{header_segment}.{expired_segment}".encode("ascii")
        expired_signature = base64.urlsafe_b64encode(hmac.new(secret.encode(), expired_signed, hashlib.sha256).digest()).decode().rstrip("=")
        with patch.dict(os.environ, config):
            self.assertIsNone(verify_token(f"{header_segment}.{expired_segment}.{expired_signature}"))

    def test_client_auth_token_endpoint(self):
        from fastapi.testclient import TestClient
        from app import app, verify_token

        client = TestClient(app)
        for method in ("get", "post"):
            response = getattr(client, method)("/api/auth/token")
            self.assertEqual(response.status_code, 200)
            data = response.json()
            self.assertIn("access_token", data)
            self.assertEqual(data["token_type"], "bearer")
            claims = verify_token(data["access_token"])
            self.assertIsNotNone(claims)
            self.assertIn("generation", claims["entitlements"])
            self.assertIn("beta_tester", claims["roles"])

    def test_generation_rate_counter_in_memory_fallback(self):
        from app import increment_generation_count

        with patch.dict(os.environ, {"REDIS_URL": ""}, clear=False), patch("riffs_api.storage.get_redis", side_effect=Exception("Redis unavailable")):
            c1 = increment_generation_count("fallback-user", now=100)
            c2 = increment_generation_count("fallback-user", now=101)
            self.assertEqual(c1, 1)
            self.assertEqual(c2, 2)


if __name__ == "__main__":
    unittest.main()
