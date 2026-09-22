"""Candidate verification safety tests: temporary files and mocked local services only."""

import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from media import digest
from store import Store, find_track
import verify_candidate as verifier


class CandidateFixture:
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / "source"
        self.store = Store(self.source)

        def media(relative):
            path = self.source / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes((relative + "-validated-fixture").encode())
            return {"status": "ready", "path": relative, "sha256": digest(path)}

        cover = {size: media(f"media/cover/{size}.jpg") for size in ["original", "400", "800"]}
        audio = {identity: media(f"media/{identity}/audio.mp3") for identity in [255, 256]}

        def ready(state):
            state["album"].update(id="official-song-collection", decision="included", cover={"status": "ready", "files": cover})
            state["album"]["edits"].update(category="International Blue Archive songs", release_date="")
            for identity in [255, 256]:
                track = find_track(state, identity)
                track.update(media=audio[identity], publish_selected=False)
                track["edits"].update(position=None, disc=None)
            state["publication"] = {"destinations": {"https://not-the-test-backend": {"receipts": {"album": {"albumId": 123}}}}}
        self.store.update(ready)

    def reject(self, message, tracks=None):
        before = self.store.database.read_bytes()
        run = self.root / "run"
        with self.assertRaisesRegex(ValueError, message):
            verifier.create_review_copy(self.source, [255, 256] if tracks is None else tracks, run)
        self.assertEqual(self.store.database.read_bytes(), before)
        self.assertFalse(run.exists())


class CandidateCopyTests(CandidateFixture, unittest.TestCase):
    def test_explicit_test_selection_does_not_approve_owner_publication_or_copy_unused_files(self):
        before = self.store.database.read_bytes()
        review, files = verifier.create_review_copy(self.source, [255], self.root / "run")
        copy = Store(review).view()
        self.assertEqual(copy["album"]["id"], "verify-run")
        self.assertEqual(copy["album"]["fields"]["category"], "International Blue Archive songs")
        self.assertEqual([track["id"] for track in copy["tracks"]], ["255"])
        self.assertTrue(copy["tracks"][0]["publish_selected"])
        self.assertIsNone(copy["tracks"][0]["fields"]["position"])
        self.assertIsNone(copy["tracks"][0]["fields"]["disc"])
        self.assertNotIn("destinations", copy["publication"])
        self.assertFalse((review / "media/256/audio.mp3").exists())
        self.assertEqual(len(files), 4)
        self.assertEqual(self.store.database.read_bytes(), before)
        self.assertFalse(find_track(self.store.read(), 255)["publish_selected"])

    def test_requires_distinct_explicit_existing_track_selection(self):
        for tracks in [[], [255, 255], [0], [True], [999]]:
            self.reject("track|source", tracks)

    def test_requires_included_idle_candidate_and_included_prepared_music(self):
        for mutate, message in [
            (lambda s: s["album"].update(decision="review"), "Include"),
            (lambda s: s["job"].update(running=True), "finish"),
            (lambda s: find_track(s, 255).update(included=False), "included music"),
            (lambda s: find_track(s, 255)["edits"].update(kind="drama"), "spoken drama"),
            (lambda s: find_track(s, 255)["media"].update(status="failed"), "Prepare every"),
        ]:
            saved = self.store.read()
            self.store.update(mutate)
            self.reject(message)
            self.store.update(lambda s: (s.clear(), s.update(saved)))

    def test_rejects_unreviewed_detail_or_index_changes(self):
        for key in ["pending_suggestions", "pending_index"]:
            self.store.update(lambda s: find_track(s, 255).update({key: {"title": "Changed"}}))
            self.reject("incoming source")
            self.store.update(lambda s: find_track(s, 255).pop(key))

    def test_rejects_missing_cover_and_tampered_or_outside_audio(self):
        saved = self.store.read()
        self.store.update(lambda s: s["album"]["cover"]["files"].pop("800"))
        self.reject("both display")
        self.store.update(lambda s: (s.clear(), s.update(saved)))
        self.store.update(lambda s: find_track(s, 255)["media"].update(sha256="wrong"))
        self.reject("validation hash")
        self.store.update(lambda s: find_track(s, 255)["media"].update(path="reviews.sqlite3", sha256="irrelevant"))
        self.reject("inside this review")

    def test_normalizes_inside_traversal_and_rechecks_copied_hashes(self):
        self.store.update(lambda s: find_track(s, 255)["media"].update(path="../source/media/255/audio.mp3"))
        review, _ = verifier.create_review_copy(self.source, [255], self.root / "normal")
        self.assertEqual(find_track(Store(review).read(), 255)["media"]["path"], "media/255/audio.mp3")
        with patch("verify_candidate.shutil.copyfile", side_effect=lambda source, target: Path(target).write_bytes(b"bad-copy")):
            with self.assertRaisesRegex(ValueError, "validation hash"):
                verifier.create_review_copy(self.source, [255], self.root / "damaged")

    def test_missing_review_does_not_initialize_it(self):
        missing = self.root / "missing"
        with self.assertRaisesRegex(ValueError, "existing prepared"):
            verifier.create_review_copy(missing, [255], self.root / "run")
        self.assertFalse(missing.exists())


class CandidateLifecycleTests(CandidateFixture, unittest.TestCase):
    def test_missing_jar_stops_before_copy_or_network(self):
        with patch.object(verifier.isolated, "JAR", self.root / "missing.jar"), \
                patch("verify_candidate.create_review_copy") as copy, patch.object(verifier.isolated, "start_server") as start:
            with self.assertRaisesRegex(RuntimeError, "Build the backend jar"):
                verifier.verify(self.source, [255])
        copy.assert_not_called()
        start.assert_not_called()

    def test_failure_stops_only_owned_backend_and_keeps_report_and_copy(self):
        process = Mock()
        jar = Mock()
        jar.is_file.return_value = True
        with patch.object(verifier.isolated, "ROOT", self.root), patch.object(verifier.isolated, "JAR", jar), \
                patch.object(verifier.isolated, "start_server", return_value=process), \
                patch.object(verifier.isolated, "stop_server") as stop, \
                patch("verify_candidate.counts", side_effect=RuntimeError("test failure")):
            with self.assertRaisesRegex(RuntimeError, "test failure"):
                verifier.verify(self.source, [255])
        stop.assert_called_once_with(process)
        report_path = next((self.root / "target").glob("*/report.json"))
        self.assertEqual(json.loads(report_path.read_text(encoding="utf-8"))["error"], "test failure")
        self.assertTrue((report_path.parent / "review/reviews.sqlite3").is_file())

    def test_busy_port_failure_does_not_stop_an_unowned_server(self):
        jar = Mock()
        jar.is_file.return_value = True
        with patch.object(verifier.isolated, "ROOT", self.root), patch.object(verifier.isolated, "JAR", jar), \
                patch.object(verifier.isolated, "start_server", side_effect=RuntimeError("Port 18082 is already in use")), \
                patch.object(verifier.isolated, "stop_server") as stop:
            with self.assertRaisesRegex(RuntimeError, "already in use"):
                verifier.verify(self.source, [255])
        stop.assert_not_called()

    def test_success_uses_fixed_destination_and_two_persisted_copy_publications(self):
        jar = Mock()
        jar.is_file.return_value = True
        process = Mock()
        attempts = []

        def publisher(store, destination, key):
            self.assertEqual((destination, key), (verifier.isolated.BASE, verifier.isolated.KEY))
            fake = Mock()
            def publish():
                attempts.append(store)
                records = {"album": {"albumId": 7, "songId": None, "revision": "a" * 64},
                           "255": {"albumId": 7, "songId": 8, "revision": "b" * 64},
                           "256": {"albumId": 7, "songId": 9, "revision": "c" * 64}}
                store.update(lambda s: s["publication"].update(
                    destinations={destination: {"receipts": records}},
                    attempt={"records": [{"record": record, "status": "unchanged"} for record in records]}))
            fake.publish.side_effect = publish
            return fake

        stable = {"object": ("unchanged-timestamp", 5, "etag")}
        before = self.store.database.read_bytes()
        with patch.object(verifier.isolated, "ROOT", self.root), patch.object(verifier.isolated, "JAR", jar), \
                patch.object(verifier.isolated, "start_server", return_value=process), \
                patch.object(verifier.isolated, "stop_server") as stop, patch("verify_candidate.Publisher", side_effect=publisher), \
                patch("verify_candidate.counts", side_effect=[[4, 10], [5, 12], [5, 12]]), \
                patch.object(verifier.isolated, "objects", side_effect=[{}, stable, stable]), \
                patch("verify_candidate.check_delivery", return_value={"id": 7}):
            report = verifier.verify(self.source, [255, 256])
        self.assertEqual(report["status"], "passed")
        self.assertEqual(len(attempts), 2)
        self.assertIsNot(attempts[0], attempts[1])
        self.assertEqual(attempts[0].directory, attempts[1].directory)
        self.assertEqual(self.store.database.read_bytes(), before)
        stop.assert_called_once_with(process)

    def test_delivery_checks_every_selected_track_and_unknown_numbering(self):
        review, _ = verifier.create_review_copy(self.source, [255, 256], self.root / "delivery")
        store = Store(review)
        store.update(lambda s: s["publication"].update(destinations={verifier.isolated.BASE: {"receipts": {
            "255": {"songId": 8}, "256": {"songId": 9}}}}))
        draft = store.view()
        songs = [{"id": song_id, "title": track["fields"]["title"], "discNumber": None, "trackNumber": None,
                  "displayOrder": track["fields"]["display_order"], "audioPath": f"audio-{song_id}.mp3", "imagePath": "cover.jpg"}
                 for song_id, track in zip([8, 9], draft["tracks"])]
        album = {"title": draft["album"]["fields"]["title"], "category": "International Blue Archive songs",
                 "releaseDate": None, "songList": songs, "coverImagePath": "album.jpg"}
        album_response = Mock(status_code=200)
        album_response.json.return_value = album
        responses = [album_response]
        for track in draft["tracks"]:
            responses += [Mock(status_code=206, headers={"Content-Type": "audio/mpeg"},
                               content=(review / track["media"]["path"]).read_bytes()),
                          Mock(status_code=200, headers={"Content-Type": "image/jpeg"})]
        responses.append(Mock(status_code=200, headers={"Content-Type": "image/jpeg"}))
        with patch.object(verifier.isolated.HTTP, "get", side_effect=responses) as get:
            self.assertEqual(verifier.check_delivery(store, 7), album)
        self.assertEqual(get.call_count, 6)
        self.assertTrue(all(call.kwargs["allow_redirects"] is False for call in get.call_args_list))


if __name__ == "__main__":
    unittest.main()
