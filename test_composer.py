import unittest

from agent import RiffsAgent
from composer import (
    compose, events_hash, parse_chord, parse_key, sanitize_events, INSTRUMENT_TIER,
)

CHORDS = ["Am", "F", "C", "G"]
BAND = ["bass_guitar", "rhythm_guitar", "cymbals"]


def lane(score, instrument):
    return next(l for l in score["lanes"] if l["instrument"] == instrument)


class TestChordParsing(unittest.TestCase):
    def test_chord_names(self):
        self.assertEqual(parse_chord("Am", "Am")["root_pc"], 9)
        self.assertEqual(parse_chord("Am", "Am")["intervals"], [0, 3, 7])
        self.assertEqual(parse_chord("Cmaj7", "C")["intervals"], [0, 4, 7, 11])
        self.assertEqual(parse_chord("G7", "C")["intervals"], [0, 4, 7, 10])
        self.assertEqual(parse_chord("Bdim", "C")["intervals"], [0, 3, 6])
        self.assertEqual(parse_chord("Dsus4", "C")["intervals"], [0, 5, 7])
        self.assertEqual(parse_chord("Bb", "F")["root_pc"], 10)

    def test_slash_bass(self):
        chord = parse_chord("C/G", "C")
        self.assertEqual((chord["root_pc"], chord["bass_pc"]), (0, 7))

    def test_nashville_numbers_follow_the_key(self):
        # In G major, vi - IV - I - V is Em - C - G - D (PRD eval case 1).
        got = [parse_chord(t, "G")["root_pc"] for t in ["6m", "4", "1", "5"]]
        self.assertEqual(got, [4, 0, 7, 2])
        self.assertEqual(parse_chord("6m", "G")["intervals"], [0, 3, 7])

    def test_nashville_and_names_agree(self):
        names = [parse_chord(t, "Am") for t in CHORDS]
        numbers = [parse_chord(t, "Am") for t in ["1m", "b6", "b3", "b7"]]
        self.assertEqual([c["root_pc"] for c in names], [c["root_pc"] for c in numbers])

    def test_bad_chord_raises(self):
        with self.assertRaises(ValueError):
            parse_chord("H#x", "Am")

    def test_parse_key(self):
        self.assertEqual(parse_key("Am"), (9, True))
        self.assertEqual(parse_key("F#m"), (6, True))
        self.assertEqual(parse_key("C"), (0, False))


class TestScoreShape(unittest.TestCase):
    def test_every_instrument_writes_in_range_notes(self):
        for inst in INSTRUMENT_TIER:
            for key, chords in (("Am", CHORDS), ("C", ["C", "Am7", "Fmaj7", "G7"]), ("G", ["6m", "4", "1", "5"])):
                score = compose(chords, key, [inst], prompt="funky neo-soul", seed=3)
                events = lane(score, inst)["events"]
                self.assertGreater(len(events), 8, inst)
                limit = score["loop_bars"] * 4
                for ev in events:
                    self.assertTrue(0 <= ev["beat"] < limit, (inst, ev))
                    self.assertTrue(0 < ev["dur"] <= 16, (inst, ev))
                    self.assertTrue(0 <= ev["midi"] <= 127 and 1 <= ev["vel"] <= 127, (inst, ev))
                self.assertEqual(events, sorted(events, key=lambda e: (e["beat"], e["midi"])))

    def test_bass_plays_the_chord_roots_on_the_downbeat(self):
        score = compose(CHORDS, "Am", ["bass_guitar"], seed=1)
        downbeats = {int(e["beat"]): e["midi"] % 12 for e in lane(score, "bass_guitar")["events"] if e["beat"] % 4 == 0}
        # Bars 1-2 are Am (A), 3-4 F, 5-6 C, 7-8 G.
        self.assertEqual([downbeats[b * 4] for b in range(8)], [9, 9, 5, 5, 0, 0, 7, 7])

    def test_loop_grows_for_long_progressions(self):
        self.assertEqual(compose(CHORDS, "Am", BAND)["loop_bars"], 8)
        self.assertEqual(compose(["C"] * 12, "C", BAND)["loop_bars"], 16)

    def test_same_inputs_are_deterministic(self):
        a = compose(CHORDS, "Am", BAND, prompt="x", seed=7)
        b = compose(CHORDS, "Am", BAND, prompt="x", seed=7)
        self.assertEqual(a, b)

    def test_genre_changes_the_feel(self):
        shuffle = compose(CHORDS, "Am", BAND, prompt="Halftime Shuffle", seed=1)
        rock = compose(CHORDS, "Am", BAND, prompt="Indie Rock", seed=1)
        self.assertEqual(shuffle["feel"]["tags"], ["halftime-shuffle"])
        self.assertEqual(rock["feel"]["tags"], ["indie-rock"])
        self.assertNotEqual(lane(shuffle, "cymbals")["hash"], lane(rock, "cymbals")["hash"])

    def test_tempo_is_not_part_of_the_score(self):
        self.assertNotIn("bpm", compose(CHORDS, "Am", BAND))


class TestSeeds(unittest.TestCase):
    def test_twenty_seeds_give_twenty_distinct_unlocked_lanes(self):
        for inst in ("rhythm_guitar", "cymbals", "bass_guitar", "tenor_sax"):
            hashes = {lane(compose(CHORDS, "Am", [inst], prompt="Neo-Soul", seed=s), inst)["hash"] for s in range(1, 21)}
            self.assertEqual(len(hashes), 20, inst)


class TestPartLocking(unittest.TestCase):
    def test_locked_bass_is_byte_identical_across_twenty_takes_and_others_move(self):
        take1 = compose(CHORDS, "Am", BAND, prompt="Neo-Soul", seed=1, locked_parts=["bass"])
        self.assertEqual(lane(take1, "bass_guitar")["source"], "locked_anchor")  # cold start
        bass_hashes, guitar_hashes, cymbal_hashes = set(), set(), set()
        previous = take1
        for seed in range(2, 22):
            previous = compose(CHORDS, "Am", BAND, prompt="Neo-Soul", seed=seed,
                               locked_parts=["bass"], previous_score=previous)
            bass = lane(previous, "bass_guitar")
            self.assertEqual(bass["source"], "locked_copy")
            self.assertEqual(bass["events"], lane(take1, "bass_guitar")["events"])
            bass_hashes.add(bass["hash"])
            guitar_hashes.add(lane(previous, "rhythm_guitar")["hash"])
            cymbal_hashes.add(lane(previous, "cymbals")["hash"])
        self.assertEqual(bass_hashes, {lane(take1, "bass_guitar")["hash"]})
        self.assertEqual(len(guitar_hashes), 20)
        self.assertEqual(len(cymbal_hashes), 20)

    def test_control_the_bass_really_changes_when_unlocked(self):
        take1 = compose(CHORDS, "Am", BAND, prompt="Neo-Soul", seed=1, locked_parts=["bass"])
        locked2 = compose(CHORDS, "Am", BAND, prompt="Neo-Soul", seed=2, locked_parts=["bass"], previous_score=take1)
        unlocked2 = compose(CHORDS, "Am", BAND, prompt="Neo-Soul", seed=2, locked_parts=[], previous_score=take1)
        self.assertEqual(lane(locked2, "bass_guitar")["hash"], lane(take1, "bass_guitar")["hash"])
        self.assertNotEqual(lane(unlocked2, "bass_guitar")["hash"], lane(take1, "bass_guitar")["hash"])
        self.assertEqual(lane(unlocked2, "bass_guitar")["source"], "generated")

    def test_lock_survives_a_json_round_trip(self):
        import json
        take1 = compose(CHORDS, "Am", BAND, seed=1, locked_parts=["bass"])
        wire = json.loads(json.dumps(take1))  # what the browser sends back
        take2 = compose(CHORDS, "Am", BAND, seed=2, locked_parts=["bass"], previous_score=wire)
        self.assertEqual(lane(take2, "bass_guitar")["hash"], lane(take1, "bass_guitar")["hash"])

    def test_lock_aliases_and_ids(self):
        for token, locked_inst in (("bass", "bass_guitar"), ("low", "bass_guitar"), ("bass_guitar", "bass_guitar"),
                                   ("lead", "rhythm_guitar"), ("drums", "cymbals")):
            score = compose(CHORDS, "Am", BAND, locked_parts=[token])
            self.assertEqual([l["instrument"] for l in score["lanes"] if l["locked"]], [locked_inst], token)

    def test_changed_instrument_or_loop_length_regenerates(self):
        take1 = compose(CHORDS, "Am", ["bass_guitar"], seed=1, locked_parts=["bass"])
        swapped = compose(CHORDS, "Am", ["contrabass"], seed=2, locked_parts=["bass"], previous_score=take1)
        self.assertEqual(lane(swapped, "contrabass")["source"], "locked_anchor")
        longer = compose(["C"] * 12, "C", ["bass_guitar"], seed=2, locked_parts=["bass"], previous_score=take1)
        self.assertEqual(lane(longer, "bass_guitar")["source"], "locked_anchor")

    def test_changing_chords_keeps_the_lock_but_warns(self):
        take1 = compose(CHORDS, "Am", BAND, seed=1, locked_parts=["bass"])
        take2 = compose(["Dm", "G", "C", "F"], "Am", BAND, seed=2, locked_parts=["bass"], previous_score=take1)
        self.assertEqual(lane(take2, "bass_guitar")["hash"], lane(take1, "bass_guitar")["hash"])
        self.assertTrue(any("chord progression changed" in w for w in take2["warnings"]))

    def test_tampered_previous_lane_is_rejected_and_regenerated(self):
        take1 = compose(CHORDS, "Am", BAND, seed=1, locked_parts=["bass"])
        bad = compose(CHORDS, "Am", BAND, seed=1, locked_parts=["bass"])
        lane(bad, "bass_guitar")["events"][0]["midi"] = 999
        take2 = compose(CHORDS, "Am", BAND, seed=2, locked_parts=["bass"], previous_score=bad)
        self.assertEqual(lane(take2, "bass_guitar")["source"], "locked_anchor")
        self.assertTrue(any("invalid" in w for w in take2["warnings"]))
        self.assertIsNone(sanitize_events([{"beat": -1, "dur": 1, "midi": 40, "vel": 90}], 8))
        self.assertIsNone(sanitize_events("nope", 8))

    def test_hash_ignores_int_vs_float_formatting(self):
        self.assertEqual(
            events_hash([{"beat": 4, "dur": 1, "midi": 40, "vel": 90}]),
            events_hash([{"beat": 4.0, "dur": 1.0, "midi": 40, "vel": 90}]),
        )


class TestAgentIntegration(unittest.TestCase):
    def test_generate_returns_playable_score(self):
        data = RiffsAgent().generate(prompt="Neo soul", key="Am", chords="Am - F - C - G", seed=1)
        self.assertEqual(data["score"]["loop_bars"], 8)
        self.assertEqual([l["instrument"] for l in data["score"]["lanes"]], BAND)
        self.assertEqual(data["nashville_chart"], ["1m", "b6", "b3", "b7"])

    def test_agent_reuses_last_take_for_locks(self):
        agent = RiffsAgent()
        t1 = agent.generate(prompt="a", locked_parts=["bass"], seed=1)
        t2 = agent.generate(prompt="a", locked_parts=["bass"], seed=2)
        self.assertEqual(lane(t1["score"], "bass_guitar")["hash"], lane(t2["score"], "bass_guitar")["hash"])
        self.assertNotEqual(lane(t1["score"], "cymbals")["hash"], lane(t2["score"], "cymbals")["hash"])
        self.assertTrue(t2["stems"][0]["locked"])

    def test_bad_chord_surfaces_as_value_error(self):
        with self.assertRaises(ValueError):
            RiffsAgent().generate(prompt="x", chords="Am - Zq - C")


if __name__ == "__main__":
    unittest.main()
