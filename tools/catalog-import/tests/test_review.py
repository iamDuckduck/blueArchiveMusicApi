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
from publisher import Publisher, PublicationConflict
from service import ReviewService
from sources import content_text, cv_names, fetch_gamekee, suggestions_from_kivo, suggestions_from_tags
from store import Store, find_track, propose_fields

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

    def test_display_order_is_saved_separately_from_unknown_official_numbers(self):
        self.store.save_edits({"tracks":{"255":{"position":None, "disc":None, "display_order":10}}})
        with patch("sources.fetch_kivo", side_effect=record):
            ReviewService(self.store).fetch_tracks()
        saved = Store(self.temp.name).view()
        fields = find_track(saved, 255)["fields"]
        self.assertEqual(fields["display_order"], 10)
        self.assertIsNone(fields["position"])
        self.assertIsNone(fields["disc"])
        for order in [None, True, 0, 1000000]:
            with self.assertRaises(ValueError):
                self.store.save_edits({"tracks":{"255":{"display_order":order}}})

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

    def test_changed_details_are_proposals_until_used_or_kept(self):
        service = ReviewService(self.store)
        with patch("sources.fetch_kivo", side_effect=record):
            service.fetch_tracks()
        before = find_track(self.store.view(), 255)["fields"]["title"]
        def updated(identity):
            data = record(identity)
            data["title"] = "Incoming corrected title"
            return data
        with patch("sources.fetch_kivo", side_effect=updated):
            service.fetch_tracks()
        row = find_track(self.store.view(), 255)
        self.assertEqual(row["fields"]["title"], before)
        self.assertEqual(row["pending_suggestions"]["kivo"]["title"], "Incoming corrected title")
        self.assertEqual(len(row["source_history"]), 1)
        self.store.review_suggestions("255", row["pending_suggestions"], "keep")
        with patch("sources.fetch_kivo", side_effect=updated):
            service.fetch_tracks()
        kept = find_track(Store(self.temp.name).view(), 255)
        self.assertEqual(kept["fields"]["title"], before)
        self.assertFalse(kept["pending_suggestions"])
        other = find_track(self.store.view(), 256)
        self.store.review_suggestions("256", other["pending_suggestions"], "use")
        self.assertEqual(find_track(self.store.view(), 256)["fields"]["title"], "Incoming corrected title")

    def test_tag_proposals_preserve_manual_credits_and_reject_stale_review_actions(self):
        self.store.save_edits({"tracks":{"255":{"composer":["Owner correction"]}}})
        self.store.update(lambda s: propose_fields(find_track(s, 255), "tags", {"composer":"Incoming composer"}, {"composer":"Old composer"}))
        row = find_track(self.store.view(), 255)
        self.assertEqual(row["fields"]["composer"], ["Owner correction"])
        self.assertEqual(row["pending_suggestions"]["tags"]["composer"], ["Incoming composer"])
        with self.assertRaises(ValueError):
            self.store.review_suggestions("255", {"tags":{"composer":["Earlier unseen value"]}}, "use")
        self.store.review_suggestions("255", row["pending_suggestions"], "use")
        self.assertEqual(find_track(self.store.view(), 255)["fields"]["composer"], ["Incoming composer"])


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

    def test_same_url_audio_refresh_validates_before_replacing_and_reuses_unchanged_bytes(self):
        content = b"first validated audio"
        def download(url, target, limit):
            target.write_bytes(content)
        def inspect(path):
            if path.read_bytes() == b"invalid":
                raise ValueError("Full decode failed")
            return {"tags":{}, "sha256":digest(path), "duration":1}
        url = "https://static.kivo.wiki/test.mp3"
        with patch("media.download", side_effect=download) as get, patch("media.inspect_audio", side_effect=inspect):
            first = prepare_audio(self.root, 1, url, {})
            old = self.root / first["path"]
            timestamp = old.stat().st_mtime_ns
            same = prepare_audio(self.root, 1, url, first, force=True)
            self.assertEqual(same["path"], first["path"])
            self.assertEqual(old.stat().st_mtime_ns, timestamp)
            content = b"invalid"
            with self.assertRaisesRegex(ValueError, "Full decode"):
                prepare_audio(self.root, 1, url, first, force=True)
            self.assertEqual(digest(old), first["sha256"])
            content = b"different validated audio"
            changed = prepare_audio(self.root, 1, url, first, force=True)
            self.assertNotEqual(changed["path"], first["path"])
            self.assertEqual(digest(old), first["sha256"])
            self.assertEqual(digest(self.root / changed["path"]), changed["sha256"])
            self.assertEqual(get.call_count, 4)
        self.assertEqual(list((self.root / "media" / "1").glob(".prepare-*")), [])

    def test_cover_refresh_preserves_original_and_all_variants_on_failure(self):
        color = "blue"
        def download(url, target, limit):
            if color == "invalid":
                target.write_bytes(b"not an image")
            else:
                Image.new("RGB", (900, 600), color).save(target)
        url = "https://static.kivo.wiki/cover.jpg"
        with patch("media.download", side_effect=download):
            first = prepare_cover(self.root, url, {})
            timestamps = {k:(self.root / f["path"]).stat().st_mtime_ns for k,f in first["files"].items()}
            self.assertEqual(prepare_cover(self.root, url, first, force=True), first)
            color = "invalid"
            with self.assertRaises(OSError):
                prepare_cover(self.root, url, first, force=True)
            color = "red"
            second = prepare_cover(self.root, url, first, force=True)
            for key, item in first["files"].items():
                self.assertEqual(digest(self.root / item["path"]), item["sha256"])
                self.assertEqual((self.root / item["path"]).stat().st_mtime_ns, timestamps[key])
                self.assertNotEqual(second["files"][key]["path"], item["path"])

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

    def test_refresh_retains_failed_files_and_only_changed_media_needs_reselection(self):
        old = {"status":"ready", "sha256":"old", "path":"media/255/old.mp3", "tags":{}}
        cover = {"status":"ready", "files":{"400":{"sha256":"old cover"}}}
        def ready(state):
            state["album"].update(decision="included", cover=cover)
            for row in state["tracks"]:
                if row["source_id"]:
                    row.update(source=record(row["source_id"]), media=old, publish_selected=True)
        self.store.update(ready)
        with patch("sources.fetch_kivo", side_effect=record), patch.object(self.service, "fetch_gamekee"), \
                patch("media.prepare_cover", side_effect=ValueError("Invalid replacement cover")), \
                patch("media.prepare_audio", side_effect=ValueError("Invalid replacement audio")):
            self.service.prepare(force=True)
        failed = self.store.read()
        self.assertEqual(failed["album"]["cover"]["status"], "ready")
        self.assertIn("Invalid replacement", failed["album"]["cover"]["error"])
        self.assertEqual(find_track(failed, 255)["media"]["path"], old["path"])
        self.assertTrue(find_track(failed, 255)["publish_selected"])
        def prepare(root, track_id, url, previous, force=False):
            self.assertTrue(force)
            return old | {"sha256":"new", "path":"media/255/new.mp3"} if track_id == "255" else old
        with patch("sources.fetch_kivo", side_effect=record), patch.object(self.service, "fetch_gamekee"), \
                patch("media.prepare_cover", return_value=cover), patch("media.prepare_audio", side_effect=prepare):
            self.service.prepare(force=True)
        changed = self.store.read()
        self.assertFalse(find_track(changed, 255)["publish_selected"])
        self.assertTrue(find_track(changed, 256)["publish_selected"])
        self.assertEqual(find_track(changed, 255)["media_history"][0]["path"], old["path"])

    def test_restart_during_refresh_restores_previous_validated_media(self):
        previous = {"status":"ready", "path":"media/255/good.mp3", "sha256":"good"}
        self.store.update(lambda s: find_track(s, 255).update(media={"status":"running", "previous":previous}))
        self.store.update(lambda s: s["album"].update(cover={"status":"running", "previous":{"status":"ready", "files":{"400":{}}}}))
        restarted = Store(self.temp.name).view()
        self.assertEqual(find_track(restarted, 255)["media"]["path"], previous["path"])
        self.assertEqual(find_track(restarted, 255)["media"]["status"], "ready")
        self.assertEqual(restarted["album"]["cover"]["status"], "ready")

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
        for item in [*state["album"]["cover"]["files"].values(), find_track(state, 255)["media"], find_track(state, 256)["media"]]:
            item["sha256"] = digest(self.store.directory / item["path"])

    def test_reviewed_release_uses_stable_put_urls_and_records_results(self):
        responses = []
        for album_id, song_id in [(7, None), (7, 8), (7, 9)]:
            response = Mock(ok=True, status_code=200)
            response.json.return_value = {"albumId":album_id, "songId":song_id, "status":"created", "revision":"a" * 64}
            responses.append(response)
        with patch("publisher.requests.put", side_effect=responses) as put:
            result = Publisher(self.store, "http://127.0.0.1:8080", "secret").publish()
        self.assertEqual(result["status"], "ready")
        self.assertEqual(put.call_count, 3)
        self.assertTrue(put.call_args_list[0].args[0].endswith("/kivo/albums/veritas-vol-2"))
        self.assertTrue(put.call_args_list[1].args[0].endswith("/kivo/albums/veritas-vol-2/tracks/255"))
        self.assertEqual(json.loads(put.call_args_list[1].kwargs["files"]["metadata"][1])["displayOrder"], 1)

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
            result.json.return_value = {"albumId": album_id, "songId": song_id, "status": "updated", "revision": "a" * 64}
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


    def test_attempt_keeps_album_success_when_first_track_conflicts(self):
        album_response = Mock(status_code=200)
        album_response.json.return_value = {"albumId":7, "songId":None, "status":"updated", "revision":"a" * 64}
        conflict_response = Mock(status_code=409)
        conflict_response.json.return_value = {"current":{
            "exists":True, "albumId":7, "songId":8, "revision":"b" * 64,
            "metadata":{"title":"Published track"}, "media":{},
        }}
        during_requests = []

        def respond(*args, **kwargs):
            during_requests.append(self.store.read()["publication"]["attempt"]["records"])
            return [album_response, conflict_response][len(during_requests) - 1]

        with patch("publisher.requests.put", side_effect=respond) as put:
            with self.assertRaisesRegex(PublicationConflict, "earlier successful records"):
                Publisher(self.store, "http://127.0.0.1:8080", "secret").publish()
        self.assertEqual(put.call_count, 2)
        self.assertEqual([item["status"] for item in during_requests[0]], ["sending", "not_sent", "not_sent"])
        self.assertEqual([item["status"] for item in during_requests[1]], ["saved", "sending", "not_sent"])
        publication = self.store.read()["publication"]
        self.assertEqual(publication["attempt"], {"destination":"http://127.0.0.1:8080", "records":[
            {"record":"album", "status":"saved"},
            {"record":"255", "status":"conflict"},
            {"record":"256", "status":"not_sent"},
        ]})
        self.assertEqual(set(publication["destinations"]["http://127.0.0.1:8080"]["receipts"]), {"album"})

    def test_attempt_resets_on_retry_and_destination_change(self):
        response = Mock(status_code=200)
        response.json.return_value = {"albumId":7, "songId":8, "status":"created", "revision":"a" * 64}
        publisher = Publisher(self.store, "http://127.0.0.1:8080", "secret")
        with patch("publisher.requests.put", return_value=response):
            publisher.publish()
        self.store.update(lambda state: find_track(state, 256).update(publish_selected=False))
        response.json.return_value["status"] = "unchanged"
        with patch("publisher.requests.put", side_effect=[response, ConnectionError("Connection lost")]):
            with self.assertRaisesRegex(ConnectionError, "Connection lost"):
                publisher.publish()
        self.assertEqual(self.store.read()["publication"]["attempt"]["records"], [
            {"record":"album", "status":"unchanged"}, {"record":"255", "status":"failed"},
        ])

        with patch("publisher.requests.put", side_effect=ConnectionError("Offline")):
            with self.assertRaises(ConnectionError):
                Publisher(self.store, "http://127.0.0.1:18082/", "secret").publish()
        publication = self.store.read()["publication"]
        self.assertEqual(publication["attempt"], {"destination":"http://127.0.0.1:18082", "records":[
            {"record":"album", "status":"failed"}, {"record":"255", "status":"not_sent"},
        ]})
        self.assertEqual(set(publication["destinations"]["http://127.0.0.1:8080"]["receipts"]), {"album", "255", "256"})

    def test_attempt_file_error_stops_before_remaining_records(self):
        self.store.update(lambda state: state["album"]["cover"]["files"]["original"].update(sha256="changed"))
        with patch("publisher.requests.put") as put:
            with self.assertRaisesRegex(ValueError, "Prepared media changed"):
                Publisher(self.store, "http://127.0.0.1:8080", "secret").publish()
        put.assert_not_called()
        self.assertEqual(self.store.read()["publication"]["attempt"]["records"], [
            {"record":"album", "status":"failed"},
            {"record":"255", "status":"not_sent"},
            {"record":"256", "status":"not_sent"},
        ])

    def test_success_clears_only_the_successful_records_conflict(self):
        destination = "http://127.0.0.1:8080"
        self.store.update(lambda state: state["publication"].update(destinations={destination:{
            "receipts":{}, "observed":{}, "conflict":"255",
        }}))
        response = Mock(status_code=200)
        response.json.return_value = {"albumId":7, "songId":8, "status":"unchanged", "revision":"a" * 64}
        conflicts_during_requests = []

        def respond(*args, **kwargs):
            conflicts_during_requests.append(self.store.read()["publication"]["destinations"][destination].get("conflict"))
            return response

        with patch("publisher.requests.put", side_effect=respond):
            Publisher(self.store, destination, "secret").publish()
        self.assertEqual(conflicts_during_requests, ["255", "255", None])
        self.assertNotIn("conflict", self.store.read()["publication"]["destinations"][destination])

    def test_accepting_album_baseline_preserves_an_unrelated_track_conflict(self):
        destination = "http://127.0.0.1:8080"
        self.store.update(lambda state: state["publication"].update(destinations={destination:{
            "receipts":{}, "conflict":"255", "observed":{
                "album":{"exists":True, "albumId":7, "songId":None, "revision":"a" * 64, "metadata":{}, "media":{}},
                "255":{"exists":True, "albumId":7, "songId":8, "revision":"b" * 64, "metadata":{}, "media":{}},
            },
        }}))
        publisher = Publisher(self.store, destination, "secret")
        publisher.accept_baseline("album", "a" * 64)
        self.assertEqual(self.store.read()["publication"]["destinations"][destination]["conflict"], "255")
        publisher.accept_baseline("255", "b" * 64)
        self.assertNotIn("conflict", self.store.read()["publication"]["destinations"][destination])

    def test_available_selected_track_publishes_while_missing_track_remains_visible(self):
        self.store.update(lambda s: find_track(s, 256).update(publish_selected=False, media={"status":"failed", "error":"Missing audio"}))
        response = Mock(status_code=200)
        response.json.return_value = {"albumId":7, "songId":8, "status":"created", "revision":"a" * 64}
        with patch("publisher.requests.put", return_value=response) as put:
            Publisher(self.store, "http://127.0.0.1:8080", "secret").publish()
        self.assertEqual(put.call_count, 2)
        missing = find_track(self.store.read(), 256)
        self.assertTrue(missing["included"])
        self.assertEqual(missing["media"]["error"], "Missing audio")
        self.assertEqual(put.call_args_list[1].kwargs["files"]["audio"][2], "audio/mpeg")

    def test_publication_baselines_are_scoped_to_destination_and_reused_on_retries(self):
        response = Mock(status_code=200)
        response.json.return_value = {"albumId":7, "songId":8, "revision":"a" * 64}
        first = Publisher(self.store, "http://127.0.0.1:8080", "secret")
        with patch("publisher.requests.put", return_value=response) as put:
            first.publish()
            first.publish()
            self.assertNotIn("X-Catalog-Revision", put.call_args_list[0].kwargs["headers"])
            for call in put.call_args_list[3:6]:
                self.assertEqual(call.kwargs["headers"]["X-Catalog-Revision"], "a" * 64)
            Publisher(self.store, "http://127.0.0.1:18082", "secret").publish()
            self.assertNotIn("X-Catalog-Revision", put.call_args_list[6].kwargs["headers"])
        destinations = Store(self.temp.name).read()["publication"]["destinations"]
        self.assertEqual(len(destinations), 2)

    def test_conflict_preserves_draft_and_needs_explicit_baseline_acceptance(self):
        publisher = Publisher(self.store, "http://127.0.0.1:8080", "secret")
        current = {"exists":True, "revision":"b" * 64, "albumId":7, "songId":None,
                   "metadata":{"title":"Newer live title"}, "media":{}}
        response = Mock(status_code=409)
        response.json.return_value = {"current":current}
        before = self.store.view()["album"]["fields"]
        with patch("publisher.requests.put", return_value=response) as put:
            with self.assertRaises(PublicationConflict):
                publisher.publish()
            self.assertEqual(put.call_count, 1)
        self.assertNotIn("X-Catalog-Revision", publisher._headers("album"))
        self.assertEqual(self.store.view()["album"]["fields"], before)
        with self.assertRaises(ValueError):
            publisher.accept_baseline("album", "old displayed token")
        publisher.accept_baseline("album", current["revision"])
        self.assertEqual(publisher._headers("album")["X-Catalog-Revision"], current["revision"])
        self.assertFalse(find_track(self.store.read(), 255)["publish_selected"])
        self.assertEqual(self.store.view()["album"]["fields"], before)

    def test_reading_live_state_does_not_advance_baselines_or_change_drafts(self):
        publisher = Publisher(self.store, "http://127.0.0.1:8080", "secret")
        response = Mock(status_code=200)
        response.json.return_value = {"exists":False, "revision":None, "metadata":{}, "media":{}}
        before = self.store.view()["tracks"]
        with patch("publisher.requests.get", return_value=response) as get:
            publisher.observe_published()
        self.assertEqual(get.call_count, 3)
        self.assertEqual(self.store.view()["tracks"], before)
        self.assertNotIn("X-Catalog-Revision", publisher._headers("255"))

    def test_unvalidated_or_outside_media_files_are_never_uploaded(self):
        publisher = Publisher(self.store, "http://127.0.0.1:8080", "secret")
        for item in [{"path":"reviews.sqlite3", "sha256":digest(self.store.database)},
                     {"path":"media/255/audio.mp3", "sha256":"changed"}]:
            with self.assertRaises(ValueError):
                publisher._open(item)

    def test_unreviewed_source_proposals_block_selected_tracks_before_any_upload(self):
        self.store.update(lambda s: find_track(s, 255).update(pending_suggestions={"kivo":{"title":"Incoming"}}))
        with patch("publisher.requests.put") as put:
            with self.assertRaisesRegex(ValueError, "incoming source"):
                Publisher(self.store, "http://127.0.0.1:8080", "secret").publish()
            put.assert_not_called()

    def test_malformed_published_snapshot_cannot_be_used_as_a_baseline(self):
        publisher = Publisher(self.store, "http://127.0.0.1:8080", "secret")
        response = Mock(status_code=200)
        response.json.return_value = {"exists":True, "metadata":{}, "media":{}}
        with patch("publisher.requests.get", return_value=response), self.assertRaises(ValueError):
            publisher.observe_published()
        self.assertEqual(publisher._destination(self.store.read())["observed"], {})


class BrowserApiTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.app = create_app(self.temp.name)
        self.client = self.app.test_client()
        self.store = self.app.extensions["review_store"]

    def test_page_and_edit_round_trip(self):
        response = self.client.get("/albums/veritas-vol-2/")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Album review", response.data)
        response = self.client.put("/api/review", json={"tracks": {"255": {"notes": "Checked locally"}}})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(find_track(response.json, 255)["fields"]["notes"], "Checked locally")

    def test_comparison_controls_load_without_demo_scaffolding(self):
        page = self.client.get("/albums/veritas-vol-2/").get_data(as_text=True)
        self.assertLess(page.index("published-comparison.js"), page.index("review.js"))
        self.assertIn('id="published-panel"', page)
        self.assertIn('id="publication-progress"', page)
        self.assertIn('id="show-matching"', page)
        self.assertIn('<a href="/catalog">Albums</a>', page)
        self.assertNotIn("demo-toolbar", page)
        for path in ["/static/published-comparison.js", "/static/review.js", "/static/review.css"]:
            response = self.client.get(path)
            self.assertEqual(response.status_code, 200)
            response.close()

    def test_confirming_baseline_only_changes_local_review_state(self):
        destination = "http://127.0.0.1:18080"
        app = create_app(self.temp.name, destination, "test-only-key")
        store = app.extensions["review_store"]
        snapshot = {"exists":True, "albumId":7, "songId":None, "revision":"a" * 64,
                    "metadata":{"title":"Published correction"}, "media":{}}
        store.update(lambda state: state["publication"].update(destinations={destination:{
            "receipts":{}, "observed":{"album":snapshot}, "conflict":"album",
        }}))
        store.update(lambda state: find_track(state, 255).update(publish_selected=True))
        before = store.view()
        with patch("publisher.requests.put") as upload, patch("publisher.requests.get") as fetch:
            response = app.test_client().post("/api/publication/baseline", json={"record":"album", "revision":snapshot["revision"]})
        upload.assert_not_called()
        fetch.assert_not_called()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["album"], before["album"])
        self.assertFalse(find_track(response.json, 255)["publish_selected"])
        saved = response.json["publication"]["destinations"][destination]
        self.assertEqual(saved["receipts"]["album"]["revision"], snapshot["revision"])
        self.assertNotIn("conflict", saved)

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
