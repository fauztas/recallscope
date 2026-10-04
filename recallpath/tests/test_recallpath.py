"""Unit tests for RecallPath ranking, uncertainty, batching, and session recovery."""

import json
import os
import unittest
from io import BytesIO
from pathlib import Path

from PIL import Image

from recallpath.services.image_analyser import analyse_photos, iter_batches
from recallpath.services.memory_interpreter import interpret_memory
from recallpath.services.retriever import rank_collection
from recallpath.utils.diagnostics import (
    fresh_diagnostics,
    mark_absent,
    mark_found,
    note_broaden,
    note_closer,
    note_not_sure,
    note_not_this,
    note_undo,
)
from recallpath.utils.errors import ProviderError, public_detail, redact
from recallpath.utils.images import add_photos, prepare_image
from recallpath.utils.narrowing import broaden, hide_photo, mark_closer, new_view, undo, visible_ids
from recallpath.utils.scoring import recognition_clues_from_photo
from recallpath.utils import config


def _png(color, size=(24, 16)):
    buffer = BytesIO()
    Image.new("RGB", size, color).save(buffer, format="PNG")
    return buffer.getvalue()


def _reading(**kwargs):
    reading = {
        "analysis_status": "ok",
        "people_count": "unknown",
        "people_arrangement": "",
        "setting": "",
        "objects": [],
        "appearance": [],
        "activity": "",
        "time_cues": "",
        "summary": "",
        "confidence": "high",
        "observations": [],
        "failure_reason": "",
    }
    reading.update(kwargs)
    return reading


def _photo(photo_id, filename, analysis):
    return {
        "id": photo_id,
        "filename": filename,
        "mime": "image/jpeg",
        "bytes": b"jpeg-bytes",
        "sha256": photo_id,
        "analysis": analysis,
    }


class MemoryTests(unittest.TestCase):
    def test_hedged_place_is_not_stored_as_fact(self):
        memory = "We were sitting outside at a cafe. I think it was Goa."

        def complete(_messages):
            return json.dumps({
                "user_stated": [
                    {"facet": "setting", "text": "Goa", "quote": "I think it was Goa"},
                    {"facet": "setting", "text": "outside at a cafe", "quote": "sitting outside at a cafe"},
                ],
                "ai_inferred": [{
                    "facet": "setting",
                    "text": "Location is Goa",
                    "basis": "They mentioned Goa",
                    "confidence": "high",
                }],
                "hedged": [],
                "missing": ["exact date"],
            })

        result = interpret_memory(memory, complete)
        stated = " ".join(item["text"].lower() for item in result["user_stated"])
        hedged = " ".join(item["text"].lower() for item in result["hedged"])
        inferred = " ".join(item["text"].lower() for item in result["ai_inferred"])
        self.assertNotIn("goa", stated)
        self.assertIn("goa", hedged)
        self.assertNotIn("goa", inferred)
        self.assertIn("cafe", stated)

    def test_ungrounded_clue_is_dropped(self):
        def complete(_messages):
            return json.dumps({
                "user_stated": [{"facet": "setting", "text": "a beach at night", "quote": "a beach at night"}],
                "hedged": [],
                "ai_inferred": [],
            })

        result = interpret_memory("We sat outside at a cafe.", complete)
        self.assertTrue(result["no_useful_clues"])

    def test_malformed_json_does_not_invent_clues(self):
        calls = {"count": 0}

        def complete(_messages):
            calls["count"] += 1
            return "not json"

        with self.assertRaises(ProviderError) as caught:
            interpret_memory("Four of us at a cafe.", complete)
        self.assertEqual(caught.exception.kind, "bad_response")
        self.assertEqual(calls["count"], 2)


class ScoringTests(unittest.TestCase):
    def _memory(self):
        return {
            "no_useful_clues": False,
            "user_stated": [
                {"id": "s1", "source": "user_stated", "facet": "people", "text": "four of us", "quote": "four of us"},
                {"id": "s2", "source": "user_stated", "facet": "setting", "text": "outside at a cafe", "quote": ""},
                {"id": "s3", "source": "user_stated", "facet": "objects", "text": "plants", "quote": ""},
                {"id": "s4", "source": "user_stated", "facet": "appearance", "text": "wearing white", "quote": ""},
            ],
            "hedged": [
                {"id": "h1", "source": "hedged", "facet": "setting", "text": "Goa", "quote": "I think it was Goa"},
            ],
            "ai_inferred": [],
        }

    def _library(self):
        cafe = _photo("cafe", "cafe.jpg", _reading(
            people_count="4",
            setting="outdoor cafe tables",
            objects=["plants"],
            appearance=["white shirt"],
            summary="Four people sitting outside at a cafe with plants",
            observations=[
                {"facet": "setting", "text": "outdoor cafe", "confidence": "high"},
                {"facet": "objects", "text": "plants", "confidence": "high"},
                {"facet": "appearance", "text": "white shirt", "confidence": "high"},
            ],
        ))
        office = _photo("office", "office.jpg", _reading(
            people_count="1",
            setting="indoor office desk",
            appearance=["black jacket"],
            summary="One person at an office desk",
            observations=[
                {"facet": "setting", "text": "office desk", "confidence": "high"},
                {"facet": "appearance", "text": "black jacket", "confidence": "high"},
            ],
        ))
        unread = _photo("unread", "unread.jpg", None)
        return [cafe, office, unread]

    def test_ranking_uses_readings_and_keeps_every_photo(self):
        ranked = rank_collection(self._memory(), self._library(), [])
        self.assertEqual([item["photo_id"] for item in ranked], ["cafe", "office", "unread"])
        by_id = {item["photo_id"]: item for item in ranked}
        self.assertGreater(by_id["cafe"]["score"], by_id["office"]["score"])
        self.assertIsNone(by_id["unread"]["score"])
        self.assertEqual(by_id["cafe"]["group"], "closer")
        self.assertTrue(by_id["cafe"]["explanation"])
        goa_judgments = [
            item for item in by_id["office"]["judgments"] if "goa" in item["clue_text"].lower()
        ]
        self.assertTrue(goa_judgments)
        self.assertTrue(all(item["points"] == 0 for item in goa_judgments))

    def test_hedged_clue_does_not_remove_a_photo(self):
        memory = {
            "no_useful_clues": False,
            "user_stated": [],
            "hedged": [{"id": "h1", "source": "hedged", "facet": "setting", "text": "Goa", "quote": "I think it was Goa"}],
            "ai_inferred": [],
        }
        photos = [
            _photo("a", "a.jpg", _reading(setting="a kitchen", summary="a kitchen", confidence="high")),
            _photo("b", "b.jpg", _reading(setting="a park", summary="a park", confidence="high")),
        ]
        ranked = rank_collection(memory, photos, [])
        self.assertEqual({item["photo_id"] for item in ranked}, {"a", "b"})
        self.assertTrue(all(item["score"] == 0 for item in ranked))

    def test_color_conflict_does_not_drop_the_photo(self):
        memory = {
            "no_useful_clues": False,
            "user_stated": [{"id": "s1", "source": "user_stated", "facet": "appearance", "text": "wearing white", "quote": ""}],
            "hedged": [],
            "ai_inferred": [],
        }
        photos = [_photo("solo", "solo.jpg", _reading(appearance=["black jacket"], summary="black jacket"))]
        ranked = rank_collection(memory, photos, [])
        self.assertEqual(ranked[0]["photo_id"], "solo")
        self.assertLess(ranked[0]["score"], 0)

    def test_recognition_clues_rerank_without_removing(self):
        memory = {"no_useful_clues": False, "user_stated": [], "hedged": [], "ai_inferred": []}
        plants = _photo("plants", "plants.jpg", _reading(
            summary="leafy plants",
            observations=[{"facet": "objects", "text": "leafy plants", "confidence": "high"}],
        ))
        desk = _photo("desk", "desk.jpg", _reading(
            summary="wooden desk",
            observations=[{"facet": "objects", "text": "wooden desk", "confidence": "high"}],
        ))
        clues = recognition_clues_from_photo(plants)
        ranked = rank_collection(memory, [desk, plants], clues)
        self.assertEqual([item["photo_id"] for item in ranked], ["plants", "desk"])

    def test_group_size_outranks_generic_outside(self):
        memory = {
            "no_useful_clues": False,
            "user_stated": [
                {"id": "s1", "source": "user_stated", "facet": "people", "text": "some friends", "quote": "some friends"},
                {"id": "s2", "source": "user_stated", "facet": "people", "text": "a few people", "quote": "There were a few people"},
            ],
            "hedged": [
                {"id": "h1", "source": "hedged", "facet": "setting", "text": "outside", "quote": "I think we were somewhere outside"},
            ],
            "ai_inferred": [
                {"id": "i1", "source": "ai_inferred", "facet": "setting", "text": "outdoor environment", "basis": "they thought it was outside", "confidence": "medium"},
            ],
        }
        group = _photo("group", "group.jpg", _reading(
            people_count="5",
            people_arrangement="several people standing together",
            setting="outdoor lawn",
            summary="several people outside",
            confidence="high",
        ))
        pair = _photo("pair", "pair.jpg", _reading(
            people_count="2",
            people_arrangement="two people",
            setting="outdoor path",
            summary="two people outside",
            confidence="high",
        ))
        indoor = _photo("indoor", "indoor.jpg", _reading(
            people_count="6",
            people_arrangement="several people sitting together",
            setting="indoor room",
            summary="several people indoors",
            confidence="high",
        ))
        ranked = rank_collection(memory, [pair, indoor, group], [])
        self.assertEqual([item["photo_id"] for item in ranked], ["group", "indoor", "pair"])
        for item in ranked:
            self.assertNotIn("friend", item["reason"].lower())
            self.assertNotIn("outdoor environment", item["reason"].lower())
        self.assertIn("people", ranked[0]["reason"].lower())
        self.assertIn("partly", ranked[2]["reason"].lower())
        outside = [entry for entry in ranked[2]["judgments"] if entry["clue_text"] == "outside"]
        self.assertTrue(outside)
        self.assertTrue(all(entry["points"] >= 0 for entry in outside))
        stated = [entry for entry in ranked[0]["judgments"] if entry["clue_text"] == "a few people" and entry["points"] > 0]
        inferred = [entry for entry in ranked[0]["judgments"] if entry["source"] == "ai_inferred" and entry["points"] > 0]
        self.assertTrue(stated)
        self.assertGreater(max(entry["points"] for entry in stated), max(entry["points"] for entry in inferred))


class NarrowingTests(unittest.TestCase):
    def test_hide_can_be_undone_and_broadened(self):
        ranked = [
            {"photo_id": "target", "group": "other"},
            {"photo_id": "other", "group": "closer"},
        ]
        view = new_view()
        hide_photo(view, "target")
        self.assertNotIn("target", visible_ids(ranked, view))
        self.assertTrue(undo(view))
        self.assertIn("target", visible_ids(ranked, view))
        hide_photo(view, "target")
        self.assertEqual(broaden(view), "broadened")
        self.assertIn("target", visible_ids(ranked, view))
        self.assertEqual(broaden(view), "already_full")

    def test_closer_hides_weaker_photos_until_undo(self):
        ranked = [
            {"photo_id": "anchor", "group": "closer"},
            {"photo_id": "weak", "group": "other"},
            {"photo_id": "unread", "group": "unchecked"},
        ]
        view = new_view()
        mark_closer(view, "anchor", [{"text": "plants", "source": "recognition"}])
        shown = visible_ids(ranked, view)
        self.assertIn("anchor", shown)
        self.assertIn("unread", shown)
        self.assertNotIn("weak", shown)
        undo(view)
        self.assertIn("weak", visible_ids(ranked, view))


class AnalyserTests(unittest.TestCase):
    def _photos(self, count):
        return [
            {"id": f"p{index}", "filename": f"{index}.jpg", "mime": "image/jpeg", "bytes": f"bytes-{index}".encode(), "analysis": None}
            for index in range(count)
        ]

    def _ok_response(self, messages):
        text = messages[1]["content"][0]["text"]
        images = [part for part in messages[1]["content"] if part.get("type") == "image_url"]
        self.assertLessEqual(len(images), 3)
        ids = [line.split("photo_id: ", 1)[1] for line in text.splitlines() if "photo_id:" in line]
        self.assertEqual(len(ids), len(images))
        photos = [{
            "photo_id": photo_id,
            "summary": "a red door",
            "setting": "doorway",
            "confidence": "high",
            "observations": [{"facet": "setting", "text": "red door", "confidence": "high"}],
        } for photo_id in ids]
        return json.dumps({"photos": photos})

    def test_batches_never_exceed_three(self):
        groups = list(iter_batches(list(range(7)), 12))
        self.assertEqual([len(group) for group in groups], [3, 3, 1])

    def test_four_photos_make_two_calls(self):
        calls = {"count": 0}

        def complete(messages):
            calls["count"] += 1
            return self._ok_response(messages)

        photos = self._photos(4)
        outcome = analyse_photos(photos, complete, batch_size=12)
        self.assertEqual(calls["count"], 2)
        self.assertIsNone(outcome["halt"])
        self.assertTrue(all(photo["analysis"]["summary"] == "a red door" for photo in photos))

    def test_bad_json_does_not_invent_a_scene(self):
        photos = self._photos(1)
        outcome = analyse_photos(photos, lambda _messages: "nope")
        self.assertEqual(photos[0]["analysis"]["analysis_status"], "failed")
        self.assertEqual(photos[0]["analysis"]["summary"], "")
        self.assertEqual(photos[0]["analysis"]["observations"], [])
        self.assertIsNone(outcome["halt"])

    def test_rate_limit_keeps_finished_photos_blank(self):
        calls = {"count": 0}

        def complete(messages):
            calls["count"] += 1
            if calls["count"] == 2:
                raise ProviderError("rate_limit", "slow down")
            return self._ok_response(messages)

        photos = self._photos(4)
        outcome = analyse_photos(photos, complete, batch_size=3)
        self.assertEqual(outcome["halt"], "rate_limit")
        self.assertEqual(photos[0]["analysis"]["analysis_status"], "ok")
        self.assertEqual(photos[2]["analysis"]["analysis_status"], "ok")
        self.assertIsNone(photos[3]["analysis"])


class ImageTests(unittest.TestCase):
    def test_resize_and_reject_unsupported(self):
        prepared = prepare_image("holiday.png", _png("red", (3000, 1800)))
        self.assertTrue(prepared["ok"])
        self.assertEqual(prepared["mime"], "image/jpeg")
        self.assertTrue(prepared["bytes"].startswith(b"\xff\xd8"))
        with Image.open(BytesIO(prepared["bytes"])) as image:
            self.assertLessEqual(max(image.size), 1280)
        gif = BytesIO()
        Image.new("RGB", (8, 8), "blue").save(gif, format="GIF")
        rejected = prepare_image("anim.gif", gif.getvalue())
        self.assertFalse(rejected["ok"])
        too_big = prepare_image("big.jpg", b"x" * (15 * 1024 * 1024 + 1))
        self.assertFalse(too_big["ok"])
        self.assertIn("15 MB", too_big["error"])

    def test_cap_duplicates_and_filenames(self):
        first = _png("red")
        second = _png("blue")
        existing = []
        duplicate_notes = add_photos(existing, [
            {"filename": "same.jpg", "data": first},
            {"filename": "same.jpg", "data": first},
            {"filename": "same.jpg", "data": second},
        ])
        self.assertEqual(len(existing), 2)
        self.assertEqual(existing[1]["filename"], "same (2).jpg")
        self.assertTrue(any("already" in note for note in duplicate_notes))
        more = [
            {"filename": f"{index}.png", "data": _png((index, 20, 0))}
            for index in range(12)
        ]
        cap_notes = add_photos(existing, more)
        self.assertEqual(len(existing), 12)
        self.assertTrue(any("12" in note for note in cap_notes))


class DiagnosticsTests(unittest.TestCase):
    def test_counters_and_found_time(self):
        diagnostics = fresh_diagnostics()
        diagnostics["started_at"] = 100.0
        note_not_this(diagnostics)
        note_closer(diagnostics)
        note_not_sure(diagnostics)
        note_broaden(diagnostics, "already_full")
        note_undo(diagnostics)
        mark_found(diagnostics, "cafe", 130.0)
        self.assertEqual(diagnostics["narrowing_interactions"], 2)
        self.assertEqual(diagnostics["not_sure_count"], 1)
        self.assertEqual(diagnostics["none_repeat_count"], 1)
        self.assertEqual(diagnostics["undo_count"], 1)
        self.assertTrue(diagnostics["found"])
        self.assertEqual(diagnostics["time_to_target_seconds"], 30.0)
        mark_absent(diagnostics)
        self.assertFalse(diagnostics["found"])
        self.assertIsNone(diagnostics["time_to_target_seconds"])


class SafetyTests(unittest.TestCase):
    def test_errors_redact_secrets_and_image_payloads(self):
        blob = "gsk_testsecret123 data:image/jpeg;base64," + ("A" * 120)
        cleaned = redact(blob)
        self.assertNotIn("gsk_testsecret123", cleaned)
        self.assertNotIn("AAAA", cleaned)
        self.assertEqual(public_detail("gsk_livekeyvalue123456"), "[REDACTED]")

    def test_batch_cap_cannot_exceed_three(self):
        previous = os.environ.get("RECALLPATH_MAX_IMAGES_PER_REQUEST")
        os.environ["RECALLPATH_MAX_IMAGES_PER_REQUEST"] = "12"
        try:
            self.assertEqual(config.max_images_per_request(), 3)
        finally:
            if previous is None:
                os.environ.pop("RECALLPATH_MAX_IMAGES_PER_REQUEST", None)
            else:
                os.environ["RECALLPATH_MAX_IMAGES_PER_REQUEST"] = previous

    def test_model_ids_are_not_hard_coded_outside_config(self):
        root = Path(__file__).resolve().parents[1]
        for path in root.rglob("*.py"):
            if path.name == "config.py" or "tests" in path.parts:
                continue
            text = path.read_text(encoding="utf-8")
            self.assertNotIn(config.VISION_MODEL, text, str(path))
            self.assertNotIn(config.TEXT_MODEL, text, str(path))


if __name__ == "__main__":
    unittest.main()
