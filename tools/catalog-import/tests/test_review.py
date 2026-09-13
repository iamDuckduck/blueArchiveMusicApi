import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from PIL import Image
from sources import content_text, cv_names, fetch_gamekee, suggestions_from_kivo, suggestions_from_tags

FIXTURES = Path(__file__).parent / "fixtures"

def record(track_id):
    return json.loads((FIXTURES / f"kivo-{track_id}.json").read_text(encoding="utf-8"))["data"]


class SourceTests(unittest.TestCase):
    def test_generic_author_is_not_guessed_to_be_composer(self):
        suggestions = suggestions_from_kivo(record(255))
        self.assertNotIn("composer", suggestions)
        self.assertEqual(len(suggestions["performers"].splitlines()), 4)

    def test_cv_parser_preserves_combined_character_actor_entries(self):
        self.assertEqual(cv_names("Group《A(CV: Actor A)、B（CV：Actor B）》"), "A (CV: Actor A)\nB (CV: Actor B)")

    def test_tags_add_explicit_composer_and_track_position(self):
        result = suggestions_from_tags({"composer": "Nor", "track": "2/3", "disc": "1/1", "album_artist": "Veritas《A(CV:X)》"})
        self.assertEqual(result, {"composer": "Nor", "position": 2, "disc": 1, "performers": "A (CV: X)", "group": "Veritas"})

    def test_gamekee_failure_is_not_reported_as_empty_success(self):
        import requests
        with patch("sources.requests.get", side_effect=requests.HTTPError("567 blocked")):
            result = fetch_gamekee()
        self.assertEqual(result["status"], "failed")
        self.assertIn("567", result["error"])
        self.assertIn("gamekee.com/ba/691994", result["url"])

    def test_source_html_is_converted_to_text(self):
        self.assertEqual(content_text('<p>Composer: Nor</p><script>bad()</script><p>A &amp; B</p>'), "Composer: Nor\nA & B")

