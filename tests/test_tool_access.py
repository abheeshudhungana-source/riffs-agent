"""Tests for least-privilege tool allowlist and execution gateway."""

import unittest
from unittest.mock import patch, MagicMock

from riffs_api.tool_access import (
    ALLOWED_TOOLS,
    TOOLS,
    call_tool,
    register_tool,
    validate_session_storage_path,
)
from riffs_api.agent_loop import RiffBuildEnvironment, run_loop


class TestToolAccessControl(unittest.TestCase):
    def test_unlisted_tools_are_denied(self):
        """Audit verification: dangerous or obsolete tools are not in the allowlist."""
        revoked_tools = [
            "session_delete",
            "storage_delete",
            "playlist_modify",
            "playlist_read",
            "analytics_read",
            "arbitrary_shell_exec",
        ]
        for tool_name in revoked_tools:
            with self.subTest(tool=tool_name):
                self.assertNotIn(tool_name, ALLOWED_TOOLS)
                with self.assertRaises(PermissionError) as ctx:
                    call_tool(tool_name, "write")
                self.assertIn(f"Tool '{tool_name}' not allowed", str(ctx.exception))

    def test_read_only_tools_reject_write_action(self):
        """Read-only tools cannot be called with action='write'."""
        read_only_tools = ["search_docs", "parse_progression", "users_lookup", "inspect_take_history"]
        for tool_name in read_only_tools:
            with self.subTest(tool=tool_name):
                self.assertEqual(ALLOWED_TOOLS[tool_name]["access"], "read")
                with self.assertRaises(PermissionError) as ctx:
                    call_tool(tool_name, "write")
                self.assertIn(f"'{tool_name}' is read-only", str(ctx.exception))

    def test_high_blast_tools_require_human_approval(self):
        """External, publishing, or destructive tools require explicit approved=True."""
        gated_tools = [
            "export_symbolic_package",
            "approve_vocal_lead",
            "remux_video",
            "send_collab_invite",
        ]
        for tool_name in gated_tools:
            with self.subTest(tool=tool_name):
                self.assertTrue(ALLOWED_TOOLS[tool_name].get("require_approval"))
                # Calling without approved flag raises PermissionError
                with self.assertRaises(PermissionError) as ctx:
                    call_tool(tool_name, "write")
                self.assertIn(f"'{tool_name}' needs approval", str(ctx.exception))

                # Calling with approved=False raises PermissionError
                with self.assertRaises(PermissionError) as ctx:
                    call_tool(tool_name, "write", approved=False)
                self.assertIn(f"'{tool_name}' needs approval", str(ctx.exception))

    def test_gated_tools_succeed_when_approved(self):
        """Gated tools execute successfully when approved=True is explicitly passed."""
        res_export = call_tool("export_symbolic_package", "write", approved=True)
        self.assertEqual(res_export.get("status"), "success")

        res_vocal = call_tool("approve_vocal_lead", "write", token="test-token", approved=True)
        self.assertEqual(res_vocal.get("status"), "vocal_approved")

        res_invite = call_tool(
            "send_collab_invite", "write",
            email="artist@band.com", session_id="ses-100", approved=True,
        )
        self.assertEqual(res_invite.get("status"), "invite_sent")
        self.assertEqual(res_invite.get("recipient"), "artist@band.com")

    def test_safe_internal_writes_do_not_require_approval(self):
        """Internal low-blast drafting tools (chat, archive, draft_score) execute without friction."""
        res_chat = call_tool("session_chat", "write", session_id="s-1", message="Try ii-V-I in C")
        self.assertTrue(res_chat.get("posted"))

        res_archive = call_tool("archive_take", "write", session_id="s-1", take_id=3)
        self.assertTrue(res_archive.get("archived"))
        self.assertTrue(res_archive.get("recoverable"))

    def test_read_tools_succeed_with_read_action(self):
        """Read tools execute and return expected outputs."""
        res_docs = call_tool("search_docs", "read", query="neo soul")
        self.assertEqual(res_docs.get("status"), "success")

        res_user = call_tool("users_lookup", "read", handle="@groovemaster")
        self.assertEqual(res_user.get("username"), "groovemaster")
        self.assertNotIn("email", res_user)

        res_prog = call_tool("parse_progression", "read", progression="Am - F - C - G", key="Am")
        self.assertEqual(res_prog.get("chord_chart"), "| Am | F | C | G |")

    def test_unregistered_tool_implementation_raises_not_implemented(self):
        """If an allowed tool has no registered function, it fails cleanly."""
        ALLOWED_TOOLS["temporary_test_tool"] = {"access": "read"}
        try:
            with self.assertRaises(NotImplementedError) as ctx:
                call_tool("temporary_test_tool", "read")
            self.assertIn("no implementation is registered", str(ctx.exception))
        finally:
            ALLOWED_TOOLS.pop("temporary_test_tool", None)

    def test_register_tool_allows_extending_custom_handlers(self):
        """register_tool can register custom handlers for permitted tools."""
        ALLOWED_TOOLS["custom_hook"] = {"access": "write", "require_approval": False}
        register_tool("custom_hook", lambda action, val: {"echo": val})
        try:
            result = call_tool("custom_hook", "write", val=42)
            self.assertEqual(result, {"echo": 42})
        finally:
            ALLOWED_TOOLS.pop("custom_hook", None)
            TOOLS.pop("custom_hook", None)

    def test_validate_session_storage_path_accepts_valid_scope(self):
        """Storage path within audio/sessions/{session_id}/ is allowed."""
        valid_path = "audio/sessions/session_123/takes/take_1.json"
        res = validate_session_storage_path(valid_path, "session_123")
        self.assertEqual(res, "audio/sessions/session_123/takes/take_1.json")

    def test_validate_session_storage_path_rejects_sibling_session_prefix(self):
        """audio/sessions/abc_other must NOT match audio/sessions/abc."""
        sibling_path = "audio/sessions/abc_other/takes/take_1.json"
        with self.assertRaises(PermissionError) as ctx:
            validate_session_storage_path(sibling_path, "abc")
        self.assertIn("escapes", str(ctx.exception))

    def test_validate_session_storage_path_rejects_path_traversal(self):
        """Paths containing .. or escaping root are rejected."""
        traversal_attempts = [
            "audio/sessions/abc/../def/take.json",
            "audio/sessions/abc/../../etc/passwd",
            "../root_bucket/file.wav",
            "/audio/sessions/def/file.wav",
        ]
        for bad_path in traversal_attempts:
            with self.subTest(path=bad_path):
                with self.assertRaises(PermissionError) as ctx:
                    validate_session_storage_path(bad_path, "abc")
                self.assertIn("escapes", str(ctx.exception))

    def test_validate_session_storage_path_rejects_missing_session_id(self):
        """Missing or empty session_id fails immediately."""
        with self.assertRaises(PermissionError) as ctx:
            validate_session_storage_path("audio/sessions/take.json", "")
        self.assertIn("Missing session_id", str(ctx.exception))

    def test_archive_take_enforces_session_path_scoping(self):
        """archive_take enforces that files stay within the session prefix."""
        # Allowed inside session
        ok_res = call_tool("archive_take", "write", session_id="session_456", take_id=1)
        self.assertTrue(ok_res.get("archived"))
        self.assertEqual(ok_res.get("path"), "audio/sessions/session_456/takes/1.json")

        # Escaping to sibling session is blocked
        with self.assertRaises(PermissionError):
            call_tool(
                "archive_take", "write",
                session_id="session_456", take_id=1,
                target_path="audio/sessions/session_456_other/takes/1.json",
            )

        # Escaping via traversal is blocked
        with self.assertRaises(PermissionError):
            call_tool(
                "archive_take", "write",
                session_id="session_456", take_id=1,
                target_path="audio/sessions/session_456/../sibling/1.json",
            )

    def test_export_symbolic_package_enforces_session_path_scoping(self):
        """export_symbolic_package enforces session path scoping when approved."""
        # Allowed inside session
        ok_res = call_tool(
            "export_symbolic_package", "write",
            session_id="session_789", approved=True,
        )
        self.assertEqual(ok_res.get("status"), "success")
        self.assertIn("audio/sessions/session_789/exports/package.zip", ok_res.get("export_url"))

        # Blocked when escaping to sibling session
        with self.assertRaises(PermissionError):
            call_tool(
                "export_symbolic_package", "write",
                session_id="session_789", approved=True,
                target_path="audio/sessions/session_789_attacker/export.zip",
            )

    def test_agent_loop_runs_through_call_tool_gateway(self):
        """The observable agent loop executes all steps through the call_tool gateway."""
        env = RiffBuildEnvironment("vi - IV - I - V", "G major", 110)
        history = run_loop(env)

        self.assertEqual(
            [entry["decision"]["action"] for entry in history],
            ["parse_progression", "draft_score", "export_symbolic"],
        )
        self.assertEqual(history[0]["state_after"]["parsed_progression"]["chord_chart"], "| Em | C | G | D |")
        self.assertEqual(history[1]["state_after"]["score"]["tempo_bpm"], 110)
        self.assertEqual(history[2]["state_after"]["status"], "completed")
        self.assertTrue(history[2]["state_after"]["export"]["audio_rendered"])


if __name__ == "__main__":
    unittest.main()
