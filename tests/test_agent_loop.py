import unittest

from riffs_api.agent_loop import RiffBuildEnvironment, run_loop
from riffs_api.routes import AgentLoopRequest, run_agent_loop_endpoint


class TestAgentLoop(unittest.TestCase):
    def test_observe_decide_act_observe_completes_symbolic_build(self):
        env = RiffBuildEnvironment("vi - IV - I - V", "G major", 110)

        history = run_loop(env)

        self.assertEqual([entry["decision"]["action"] for entry in history], [
            "parse_progression", "draft_score", "export_symbolic",
        ])
        self.assertEqual(history[0]["state_after"]["parsed_progression"]["chord_chart"], "| Em | C | G | D |")
        self.assertEqual(history[1]["state_after"]["score"]["tempo_bpm"], 110)
        self.assertEqual(history[2]["state_after"]["status"], "completed")
        self.assertEqual(
            history[2]["state_after"]["export"]["files"],
            [
                "manifest.json",
                "riff_Gmaj_110bpm.mid",
                "riff_Gmaj_110bpm.musicxml",
                "riff_Gmaj_110bpm_chord_chart.json",
            ],
        )
        self.assertFalse(history[2]["state_after"]["export"]["audio_rendered"])

    def test_api_runs_loop_and_returns_observations_after_each_action(self):
        body = run_agent_loop_endpoint(AgentLoopRequest(
            progression="vi - IV - I - V",
            key="G major",
            tempo_bpm=110,
        ))
        self.assertEqual(body["status"], "completed")
        self.assertEqual(body["step_count"], 3)
        self.assertEqual(body["final_state"]["parsed_progression"]["chord_chart"], "| Em | C | G | D |")
        self.assertTrue(all("state_after" in entry for entry in body["history"]))

    def test_parse_failure_is_observed_and_decide_requests_clarification(self):
        for progression, key in (("vi - IV - I - V", None), ("H - IV - I - V", "G major")):
            with self.subTest(progression=progression, key=key):
                history = run_loop(RiffBuildEnvironment(progression, key, 110))

                self.assertEqual(
                    [entry["decision"]["action"] for entry in history],
                    ["parse_progression", "request_clarification"],
                )
                self.assertEqual(history[0]["state_after"]["status"], "parse_failed")
                self.assertFalse(history[0]["state_after"]["done"])
                self.assertEqual(history[1]["state"]["status"], "parse_failed")
                self.assertEqual(history[1]["decision"]["args"]["reason"], history[0]["result"]["error"])
                self.assertEqual(history[1]["state_after"]["status"], "awaiting_input")
                self.assertTrue(history[1]["state_after"]["done"])

    def test_unsafe_prompt_is_logged_and_refused_before_drafting(self):
        body = run_agent_loop_endpoint(AgentLoopRequest(
            progression="I - IV - V - vi",
            key="C major",
            tempo_bpm=100,
            prompt="Write lyrics for a complete song.",
        ))

        self.assertEqual(body["status"], "refused")
        self.assertEqual(body["step_count"], 1)
        self.assertEqual(body["history"][0]["state"]["status"], "unsafe_request")
        self.assertEqual(body["history"][0]["decision"]["action"], "refuse")
        self.assertEqual(body["history"][0]["state_after"]["status"], "refused")
        self.assertIsNone(body["final_state"]["parsed_progression"])
        self.assertIsNone(body["final_state"]["score"])
        self.assertIsNone(body["final_state"]["export"])


if __name__ == "__main__":
    unittest.main()
