import unittest
from agent import parse_chord_tokens, calculate_nashville_numbers, generate_tab_score, RiffsAgent

class TestRiffsAgentDay1(unittest.TestCase):
    def test_chord_token_parsing(self):
        tokens = parse_chord_tokens("Am - F - C - G")
        self.assertEqual(tokens, ["Am", "F", "C", "G"])

    def test_empty_chord_defaults(self):
        tokens = parse_chord_tokens("")
        self.assertEqual(tokens, ["Am", "F", "C", "G"])

    def test_nashville_calculation_minor(self):
        # In Am: Am is 1m, F is b6, C is b3, G is b7
        tokens = ["Am", "F", "C", "G"]
        chart = calculate_nashville_numbers(tokens, key="Am")
        self.assertEqual(chart, ["1m", "b6", "b3", "b7"])

    def test_nashville_calculation_major(self):
        # In C: C is 1, F is 4, G is 5, Am is 6m
        tokens = ["C", "F", "G", "Am"]
        chart = calculate_nashville_numbers(tokens, key="C")
        self.assertEqual(chart, ["1", "4", "5", "6m"])

    def test_nashville_preserves_numbers(self):
        tokens = ["1", "4", "5", "1"]
        chart = calculate_nashville_numbers(tokens, key="C")
        self.assertEqual(chart, ["1", "4", "5", "1"])

    def test_tab_generation(self):
        tab = generate_tab_score(["Am", "F", "C", "G"])
        self.assertIn("e|", tab)
        self.assertIn("E|", tab)
        self.assertEqual(len(tab.strip().split("\n")), 6)

    def test_agent_bpm_clamping(self):
        agent = RiffsAgent()
        res_low = agent.generate(prompt="slow", key="C", bpm=40)
        self.assertEqual(res_low["bpm"], 60)
        res_high = agent.generate(prompt="fast", key="C", bpm=250)
        self.assertEqual(res_high["bpm"], 200)

    def test_agent_generate_data_contract_and_locking(self):
        agent = RiffsAgent()
        # Take 1
        t1 = agent.generate(
            prompt="Neo soul groove",
            key="Am",
            bpm=110,
            chords="Am - F - C - G",
            instruments=["bass_guitar", "rhythm_guitar", "cymbals"],
            locked_parts=["bass_guitar"]
        )

        self.assertEqual(t1["key"], "Am")
        self.assertEqual(t1["bpm"], 110)
        self.assertEqual(t1["nashville_chart"], ["1m", "b6", "b3", "b7"])
        self.assertIn("license_certificate", t1)
        self.assertIsNone(t1["license_certificate"]["license_id"])
        self.assertEqual(t1["license_certificate"]["status"], "not_issued")

        # Check stems
        stems = t1["stems"]
        self.assertEqual(len(stems), 3)
        self.assertEqual(stems[0]["filename"], "riff_Am_110bpm_bass_guitar.mid")
        self.assertTrue(stems[0]["locked"])
        self.assertFalse(stems[1]["locked"])

        # Take 2: part locking stack preserved in take_history
        t2 = agent.generate(
            prompt="Neo soul variation",
            key="Am",
            bpm=115,
            chords="Am - F - C - G",
            instruments=["bass_guitar", "rhythm_guitar", "cymbals"],
            locked_parts=["bass_guitar"]
        )
        self.assertEqual(len(agent.take_history), 2)
        self.assertEqual(agent.take_history[0]["take_id"], 1)
        self.assertEqual(agent.take_history[1]["take_id"], 2)

if __name__ == "__main__":
    unittest.main()
