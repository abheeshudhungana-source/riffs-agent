"""Tests for the least-privilege tool allowlist and execution gateway."""

import unittest

from riffs_api.agent_loop import RiffBuildEnvironment, run_loop
from riffs_api.tool_access import ALLOWED_TOOLS, TOOLS, call_tool, register_tool


class TestToolAccessControl(unittest.TestCase):
    def test_allowlist_matches_current_agent_loop_needs(self):
        self.assertEqual(
            ALLOWED_TOOLS,
            {
                "parse_progression": {"access": "read"},
                "draft_score": {"access": "write"},
                "export_symbolic": {"access": "write"},
            },
        )

    def test_unneeded_and_high_impact_tools_are_denied(self):
        denied_tools = [
            "search_docs", "users_lookup", "inspect_take_history", "session_chat",
            "archive_take", "export_symbolic_package", "approve_vocal_lead",
            "remux_video", "send_collab_invite", "session_delete", "storage_delete",
            "playlist_modify", "playlist_read", "analytics_read", "arbitrary_shell_exec",
        ]
        for tool_name in denied_tools:
            with self.subTest(tool=tool_name):
                with self.assertRaises(PermissionError):
                    call_tool(tool_name, "write", approved=True)

    def test_read_only_tools_reject_write_action(self):
        with self.assertRaisesRegex(PermissionError, "parse_progression.*read-only"):
            call_tool("parse_progression", "write", progression="Am - F - C - G")

    def test_invalid_action_is_denied(self):
        with self.assertRaisesRegex(PermissionError, "Action must be"):
            call_tool("draft_score", "execute", progression="Am - F - C - G")

    def test_registered_handler_does_not_grant_permission(self):
        register_tool("custom_hook", lambda action: {"action": action})
        try:
            with self.assertRaises(PermissionError):
                call_tool("custom_hook", "read")
        finally:
            TOOLS.pop("custom_hook", None)

    def test_allowed_tool_without_handler_fails_closed(self):
        ALLOWED_TOOLS["temporary_test_tool"] = {"access": "read"}
        try:
            with self.assertRaisesRegex(NotImplementedError, "no implementation is registered"):
                call_tool("temporary_test_tool", "read")
        finally:
            ALLOWED_TOOLS.pop("temporary_test_tool", None)

    def test_agent_loop_runs_through_call_tool_gateway(self):
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
