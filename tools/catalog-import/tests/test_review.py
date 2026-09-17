import json
import shutil
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from PIL import Image

from app import create_app
from media import digest, inspect_audio, prepare_audio, prepare_cover, resize_cover
from publisher import Publisher
from service import ReviewService
from sources import content_text, cv_names, fetch_gamekee, suggestions_from_kivo, suggestions_from_tags
from store import Store, find_track

FIXTURES = Path(__file__).parent / "fixtures"


def record(track_id):
    return json.loads((FIXTURES / f"kivo-{track_id}.json").read_text(encoding="utf-8"))["data"]


class SavedReviewTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = Store(self.temp.name)

    def test_manual_edits_survive_source_refresh_and_restart(self):
        self.store.save_edits({"album": {"title": "Reviewed release title"}, "tracks": {"255": {"composer": "Reviewed composer"}}})
        service = ReviewService(self.store)
        with patch("sources.fetch_kivo", side_effect=record):
            service.fetch_tracks()
        restarted = Store(self.temp.name)
        result = restarted.view()
        self.assertEqual(result["album"]["fields"]["title"], "Reviewed release title")
        self.assertEqual(find_track(result, 255)["fields"]["composer"], ["Reviewed composer"])
        self.assertEqual(find_track(result, 255)["source"]["author"], "Veritas")

    def test_interrupted_work_becomes_retryable_without_losing_edits(self):
        self.store.save_edits({"tracks": {"255": {"notes": "Remember this correction"}}})
        self.store.update(lambda s: s["job"].update(running=True))
        self.store.update(lambda s: find_track(s, 255)["media"].update(status="running"))
        state = Store(self.temp.name).view()
        self.assertFalse(state["job"]["running"])
        self.assertEqual(find_track(state, 255)["media"]["status"], "failed")
        self.assertEqual(find_track(state, 255)["fields"]["notes"], "Remember this correction")

    def test_classifying_drama_excludes_it(self):
        self.store.save_edits({"tracks": {"255": {"kind": "drama"}}})
        self.assertFalse(find_track(self.store.read(), 255)["included"])
        self.assertFalse(find_track(self.store.read(), "drama")["included"])

    def test_invalid_edit_is_atomic(self):
        with self.assertRaises(ValueError):
            self.store.save_edits({"album": {"title": "Must not save"}, "tracks": {"255": {"position": -1}}})
        self.assertNotEqual(self.store.view()["album"]["fields"]["title"], "Must not save")

    def test_old_credit_text_is_preserved_as_individual_entries(self):
        self.store.update(lambda s: find_track(s, 255)["edits"].update(
            group="Veritas", composer="Nor\nAnother composer", performers="チヒロ (CV: 山村響)\nUnresolved credit"))
        fields = Store(self.temp.name).view()["tracks"][0]["fields"]
        self.assertEqual(fields["group"], ["Veritas"])
        self.assertEqual(fields["composer"], ["Nor", "Another composer"])
        self.assertEqual(fields["performers"], [{"character":"チヒロ", "voice_actor":"山村響"},
                                               {"character":"Unresolved credit", "voice_actor":""}])

    def test_multiple_and_removed_credits_survive_refresh_and_restart(self):
        credits = {"group":["Veritas", "Guest unit"], "composer":[],
                   "performers":[{"character":"チヒロ", "voice_actor":"山村響"},
                                 {"character":"Guest character", "voice_actor":""}]}
        self.store.save_edits({"tracks":{"255":credits}})
        with patch("sources.fetch_kivo", side_effect=record):
            ReviewService(self.store).fetch_tracks()
        self.store.update(lambda s: find_track(s, 255)["suggestions"].update(composer="Nor"))
        fields = Store(self.temp.name).view()["tracks"][0]["fields"]
        for key, value in credits.items():
            self.assertEqual(fields[key], value)

    def test_invalid_credit_rows_do_not_save_partial_edits(self):
        for invalid in [{"composer":[{"name":"Nor"}]}, {"performers":[{"character":"A"}]},
                        {"group":["a"] * 101}]:
            with self.assertRaises(ValueError):
                self.store.save_edits({"album":{"title":"Must not save"}, "tracks":{"255":invalid}})
            self.assertNotEqual(self.store.view()["album"]["fields"]["title"], "Must not save")


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


class ServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = Store(self.temp.name)
        self.service = ReviewService(self.store)

    def test_album_must_be_included_before_preparation(self):
        with self.assertRaises(ValueError):
            self.service.start("prepare")
        self.assertFalse(self.service.job_lock.locked())

    def test_one_failed_file_does_not_hide_the_other_and_tags_respect_edits(self):
        self.store.update(lambda s: s["album"].update(decision="included"))
        self.store.save_edits({"tracks": {"256": {"composer": "My correction"}}})
        def audio(root, track_id, url, previous):
            if track_id == "255":
                raise ValueError("Missing audio")
            return {"status": "ready", "tags": {"composer": "Nor"}, "duration": 192}
        with patch("sources.fetch_kivo", side_effect=record), patch("sources.fetch_gamekee", return_value={"status":"failed", "error":"567"}), patch("media.prepare_cover", return_value={"status":"ready"}), patch("media.prepare_audio", side_effect=audio):
            self.service.start("prepare")
            self.service.thread.join(5)
        state = self.store.view()
        self.assertFalse(state["job"]["running"])
        self.assertEqual(find_track(state, 255)["media"]["status"], "failed")
        self.assertEqual(find_track(state, 256)["media"]["status"], "ready")
        self.assertEqual(find_track(state, 256)["fields"]["composer"], ["My correction"])
        self.assertEqual(find_track(state, 256)["suggestions"]["composer"], "Nor")

    def test_repeated_gamekee_failures_keep_last_successful_text(self):
        self.store.update(lambda s: s.update(gamekee={"status": "ready", "text": "Saved credits"}))
        with patch("sources.fetch_gamekee", side_effect=lambda url: {"status": "failed", "error": "567"}):
            self.service.fetch_gamekee(force=True)
            self.service.fetch_gamekee(force=True)
        self.assertEqual(self.store.read()["gamekee"]["cached_text"], "Saved credits")

    def test_duplicate_jobs_are_rejected_and_gamekee_is_cached(self):
        entered, release = threading.Event(), threading.Event()
        def fetch(track_id):
            entered.set()
            release.wait(3)
            return record(track_id)
        with patch("sources.fetch_kivo", side_effect=fetch), patch("sources.fetch_gamekee", return_value={"status":"failed", "error":"567"}) as gamekee:
            self.service.start("fetch")
            self.assertTrue(entered.wait(2))
            with self.assertRaises(ValueError):
                self.service.start("fetch")
            release.set()
            self.service.thread.join(5)
            self.service.start("fetch")
            self.service.thread.join(5)
            gamekee.assert_called_once()


class PublisherTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = Store(self.temp.name)
        root = Path(self.temp.name)
        for relative in ["media/cover/original.png", "media/cover/cover-400.jpg",
                         "media/cover/cover-800.jpg", "media/255/audio.mp3", "media/256/audio.mp3"]:
            target = root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(b"media")
        self.store.update(lambda state: self._ready(state))

    def _ready(self, state):
        state["album"].update(decision="included", cover={"status":"ready", "files":{
            "original":{"path":"media/cover/original.png"},
            "400":{"path":"media/cover/cover-400.jpg"},
            "800":{"path":"media/cover/cover-800.jpg"}}})
        find_track(state, 255)["media"] = {"status":"ready", "path":"media/255/audio.mp3"}
        find_track(state, 256)["media"] = {"status":"ready", "path":"media/256/audio.mp3"}

    def test_reviewed_release_uses_stable_put_urls_and_records_results(self):
        responses = []
        for album_id, song_id in [(7, None), (7, 8), (7, 9)]:
            response = Mock(ok=True, status_code=200)
            response.json.return_value = {"albumId":album_id, "songId":song_id, "status":"created"}
            responses.append(response)
        with patch("publisher.requests.put", side_effect=responses) as put:
            result = Publisher(self.store, "http://127.0.0.1:8080", "secret").publish()
        self.assertEqual(result["status"], "ready")
        self.assertEqual(put.call_count, 3)
        self.assertTrue(put.call_args_list[0].args[0].endswith("/kivo/albums/veritas-vol-2"))
        self.assertTrue(put.call_args_list[1].args[0].endswith("/kivo/albums/veritas-vol-2/tracks/255"))

    def test_publish_failure_is_visible_and_retryable(self):
        failing = Mock()
        failing.publish.side_effect = ValueError("track failed")
        service = ReviewService(self.store, failing)
        service.start("publish")
        service.thread.join(5)
        publication = self.store.read()["publication"]
        self.assertEqual(publication["status"], "failed")
        self.assertIn("Safe to retry", publication["message"])

    def test_partial_success_survives_restart_and_retry_uses_same_urls(self):
        def response(album_id, song_id):
            result = Mock(status_code=200)
            result.json.return_value = {"albumId": album_id, "songId": song_id, "status": "updated"}
            return result

        failure = Mock(status_code=500, text="temporary track failure")
        with patch("publisher.requests.put", side_effect=[response(7, None), response(7, 8), failure]) as put:
            with self.assertRaisesRegex(ValueError, "500"):
                Publisher(self.store, "http://127.0.0.1:8080", "secret").publish()
            original_urls = [call.args[0] for call in put.call_args_list]

        reopened = Store(self.temp.name)
        saved = reopened.read()["publication"]
        self.assertEqual(saved["album"]["albumId"], 7)
        self.assertEqual(saved["tracks"]["255"]["songId"], 8)
        self.assertNotIn("256", saved["tracks"])
        with patch("publisher.requests.put", side_effect=[response(7, None), response(7, 8), response(7, 9)]) as put:
            result = Publisher(reopened, "http://127.0.0.1:8080", "secret").publish()
            self.assertEqual([call.args[0] for call in put.call_args_list], original_urls)
            self.assertTrue(all(call.kwargs["allow_redirects"] is False for call in put.call_args_list))
        self.assertEqual(result["status"], "ready")
        self.assertEqual(result["tracks"]["255"]["songId"], 8)
        self.assertEqual(result["tracks"]["256"]["songId"], 9)


    def test_available_selected_track_publishes_while_missing_track_remains_visible(self):
        self.store.update(lambda s: find_track(s, 256).update(publish_selected=False, media={"status":"failed", "error":"Missing audio"}))
        response = Mock(status_code=200)
        response.json.return_value = {"albumId":7, "songId":8, "status":"created"}
        with patch("publisher.requests.put", return_value=response) as put:
            Publisher(self.store, "http://127.0.0.1:8080", "secret").publish()
        self.assertEqual(put.call_count, 2)
        missing = find_track(self.store.read(), 256)
        self.assertTrue(missing["included"])
        self.assertEqual(missing["media"]["error"], "Missing audio")
        self.assertEqual(put.call_args_list[1].kwargs["files"]["audio"][2], "audio/mpeg")


class BrowserApiTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.app = create_app(self.temp.name)
        self.client = self.app.test_client()
        self.store = self.app.extensions["review_store"]

    def test_page_and_edit_round_trip(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Album review", response.data)
        response = self.client.put("/api/review", json={"tracks": {"255": {"notes": "Checked locally"}}})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(find_track(response.json, 255)["fields"]["notes"], "Checked locally")

    def test_foreign_origin_and_host_cannot_mutate_review(self):
        self.assertEqual(self.client.post("/api/decision", json={"decision":"included"}, headers={"Origin":"https://example.com"}).status_code, 403)
        self.assertEqual(self.client.get("/api/review", headers={"Host":"example.com"}).status_code, 403)
        self.assertEqual(self.client.post("/api/decision", data={"decision":"included"}).status_code, 415)

    def test_audio_range_requests_and_no_database_download(self):
        audio = Path(self.temp.name) / "media" / "255" / "audio.mp3"
        audio.parent.mkdir(parents=True)
        audio.write_bytes(b"abcdefghij")
        self.store.update(lambda s: find_track(s, 255).update(media={"status":"ready", "path":"media/255/audio.mp3"}))
        response = self.client.get("/media/audio/255", headers={"Range":"bytes=2-5"})
        self.assertEqual(response.status_code, 206)
        self.assertEqual(response.data, b"cdef")
        response.close()
        self.assertEqual(self.client.get("/data/reviews.sqlite3").status_code, 404)
        self.assertEqual(self.client.get("/media/cover/reviews.sqlite3").status_code, 404)


if __name__ == "__main__":
    unittest.main()
