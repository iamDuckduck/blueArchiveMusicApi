import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from PIL import Image
from sources import content_text, cv_names, fetch_gamekee, suggestions_from_kivo, suggestions_from_tags
from media import digest, inspect_audio, prepare_audio, prepare_cover, resize_cover

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


class MediaTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def test_cover_dimensions_original_retention_and_no_upscale(self):
        original = self.root / "original.png"
        Image.new("RGB", (1200, 600), "blue").save(original)
        original_hash = digest(original)
        result = resize_cover(original, self.root / "resized")
        self.assertEqual((result["400"]["width"], result["400"]["height"]), (400, 200))
        self.assertEqual((result["800"]["width"], result["800"]["height"]), (800, 400))
        self.assertEqual(digest(original), original_hash)
        Image.new("RGB", (100, 50), "blue").save(original)
        result = resize_cover(original, self.root / "small")
        self.assertEqual((result["800"]["width"], result["800"]["height"]), (100, 50))

    def test_ready_cover_is_not_downloaded_or_resized_again(self):
        def write_image(url, target, limit):
            target.parent.mkdir(parents=True, exist_ok=True)
            Image.new("RGB", (1100, 900), "blue").save(target)
        with patch("media.download", side_effect=write_image) as download:
            first = prepare_cover(self.root, "https://static.kivo.wiki/cover.jpg", {"status": "pending"})
            second = prepare_cover(self.root, "https://static.kivo.wiki/cover.jpg", first)
        self.assertEqual(first, second)
        download.assert_called_once()

    def test_audio_cache_is_reused_but_modified_file_is_reprepared(self):
        def write_audio(url, target, limit):
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(b"audio")
        def inspect(path):
            return {"tags": {}, "duration": 1, "sha256": digest(path), "bytes": path.stat().st_size}
        with patch("media.download", side_effect=write_audio) as download, patch("media.inspect_audio", side_effect=inspect) as probe:
            first = prepare_audio(self.root, 255, "https://static.kivo.wiki/test.mp3", {"status": "pending"})
            prepare_audio(self.root, 255, "https://static.kivo.wiki/test.mp3", first)
            self.assertEqual(download.call_count, 1)
            self.assertEqual(probe.call_count, 1)
            (self.root / first["path"]).write_bytes(b"changed")
            prepare_audio(self.root, 255, "https://static.kivo.wiki/test.mp3", first)
            self.assertEqual(download.call_count, 2)

    @unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "FFmpeg is not installed")
    def test_html_named_mp3_fails_real_audio_validation(self):
        bad = self.root / "bad.mp3"
        bad.write_text("<html>This is not an audio file</html>")
        with self.assertRaises(ValueError):
            inspect_audio(bad)

