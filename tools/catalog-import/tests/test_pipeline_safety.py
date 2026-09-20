"""Regression checks for real operator boundaries; no network or cloud writes."""

import tempfile
import unittest
from unittest.mock import patch

from app import create_app
from service import ReviewService
from store import Store, find_track
from publisher import Publisher


class PipelineSafetyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = Store(self.temp.name)

    def test_restart_marks_inflight_publication_unconfirmed_and_preserves_receipts(self):
        receipt = {"albumId": 5, "revision": "a" * 64}
        def interrupt(state):
            state["job"] = {"running": True, "action": "publish"}
            state["publication"] = {
                "status": "running", "album": receipt,
                "destinations": {"http://127.0.0.1:18082": {"receipts": {"album": receipt}}},
                "attempt": {"records": [
                    {"record": "album", "status": "saved"},
                    {"record": "255", "status": "sending"},
                    {"record": "256", "status": "not_sent"}]}}
        self.store.update(interrupt)
        state = Store(self.temp.name).read()
        self.assertFalse(state["job"]["running"])
        self.assertEqual(state["publication"]["status"], "interrupted")
        self.assertEqual([row["status"] for row in state["publication"]["attempt"]["records"]],
                         ["saved", "unconfirmed", "not_sent"])
        self.assertEqual(state["publication"]["destinations"]["http://127.0.0.1:18082"]["receipts"]["album"], receipt)
        self.assertIn("may already be saved", state["publication"]["message"])

    def test_completed_publication_is_not_reset_on_restart(self):
        self.store.update(lambda state: state["publication"].update(status="ready", message="Published"))
        self.assertEqual(Store(self.temp.name).read()["publication"]["status"], "ready")

    def test_cover_comes_from_included_music_not_first_excluded_track(self):
        def prepare(state):
            for identity in [255, 256]:
                find_track(state, identity)["source"] = {"cover": f"https://static.kivo.wiki/{identity}.jpg"}
            find_track(state, 255)["included"] = False
        self.store.update(prepare)
        service = ReviewService(self.store)
        with patch.object(service, "fetch_tracks"), patch.object(service, "fetch_gamekee"), \
                patch("media.prepare_cover", return_value={"status": "ready", "files": {}}) as cover:
            service.prepare()
        self.assertEqual(cover.call_args.args[1], "https://static.kivo.wiki/256.jpg")

    def test_failed_gamekee_refresh_retains_matching_cached_evidence_and_manual_notes(self):
        self.store.save_edits({"album": {"gamekee_notes": "Checked manually: anniversary song, not a formal album."}})
        prior = {"status": "ready", "url": "https://www.gamekee.com/ba/691994.html",
                 "text": "Reviewed reference", "checked_at": "earlier", "evidence": {"credits": []}}
        self.store.update(lambda state: state.update(gamekee=prior))
        with patch("sources.fetch_gamekee", return_value={"status": "failed", "text": "", "error": "567", "checked_at": "now"}):
            ReviewService(self.store).fetch_gamekee(force=True)
        state = Store(self.temp.name).view()
        self.assertEqual(state["gamekee"]["cached_text"], "Reviewed reference")
        self.assertEqual(state["gamekee"]["cached_checked_at"], "earlier")
        self.assertEqual(state["gamekee"]["cached_evidence"], {"credits": []})
        self.assertIn("Checked manually", state["album"]["fields"]["gamekee_notes"])
        self.store.save_edits({"album": {"gamekee_url": "https://www.gamekee.com/ba/123.html"}})
        with patch("sources.fetch_gamekee", return_value={"status": "failed", "text": "", "error": "offline"}):
            ReviewService(self.store).fetch_gamekee(force=True)
        self.assertNotIn("cached_text", self.store.read()["gamekee"])

    def test_excluding_then_reincluding_does_not_restore_publication_approval(self):
        app = create_app(self.temp.name)
        client = app.test_client()
        self.store.update(lambda state: find_track(state, 255).update(publish_selected=True))
        self.assertEqual(client.post("/api/tracks/255/inclusion", json={"included": False}).status_code, 200)
        self.assertEqual(client.post("/api/tracks/255/inclusion", json={"included": True}).status_code, 200)
        self.assertFalse(find_track(self.store.read(), 255)["publish_selected"])

    def valid_state(self):
        state = self.store.view()
        state["album"].update(decision="included", cover={"status": "ready", "files": dict.fromkeys(["original", "400", "800"], {})})
        for track in state["tracks"]:
            if track["included"]:
                track.update(publish_selected=True, media={"status": "ready", "path": "media/test.mp3"})
        return state

    def test_required_fields_and_date_are_checked_before_network_requests(self):
        publisher = Publisher(self.store, "http://127.0.0.1:18082", "test-only")
        for field, value in [("title", " "), ("category", ""), ("release_date", "2026-02-31")]:
            state = self.valid_state()
            state["album"]["fields"][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError), patch("publisher.requests.put") as put:
                publisher._publish(state)
            put.assert_not_called()
        state = self.valid_state()
        state["tracks"][1]["fields"]["title"] = " "
        with self.assertRaisesRegex(ValueError, "selected track"), patch("publisher.requests.put") as put:
            publisher._publish(state)
        put.assert_not_called()

    def test_pending_source_index_blocks_publication_but_missing_index_does_not(self):
        publisher = Publisher(self.store, "http://127.0.0.1:18082", "test-only")
        state = self.valid_state()
        state["tracks"][0]["pending_index"] = {"title": "Incoming title"}
        with self.assertRaisesRegex(ValueError, "source index changed"):
            publisher._validate(state)
        del state["tracks"][0]["pending_index"]
        state["tracks"][0]["missing_index"] = True
        publisher._validate(state)

    def test_new_audio_url_requires_preparation_without_discarding_old_file(self):
        state = self.valid_state()
        track = state["tracks"][0]
        track["source"] = {"file": "//static.kivo.wiki/new.mp3"}
        track["media"]["source_url"] = "https://static.kivo.wiki/old.mp3"
        publisher = Publisher(self.store, "http://127.0.0.1:18082", "test-only")
        with patch("publisher.requests.put") as put, self.assertRaisesRegex(ValueError, "audio URL changed"):
            publisher._publish(state)
        put.assert_not_called()
        self.assertEqual(track["media"]["path"], "media/test.mp3")
        track["publish_selected"] = False
        publisher._validate(state)  # Another ready track may still publish.
        track["publish_selected"] = True
        track["media"]["source_url"] = "https://static.kivo.wiki/new.mp3"
        publisher._validate(state)

    def test_api_rejects_selection_with_changed_source_audio(self):
        app = create_app(self.temp.name)
        self.store.update(lambda state: find_track(state, 255).update(
            source={"file": "https://static.kivo.wiki/new.mp3"},
            media={"status": "ready", "path": "media/old.mp3", "source_url": "https://static.kivo.wiki/old.mp3"}))
        response = app.test_client().post("/api/tracks/255/publication", json={"selected": True})
        self.assertEqual(response.status_code, 400)
        self.assertIn("prepare changed audio", response.get_json()["error"])

    def test_open_review_sees_rescan_before_poll_and_before_publish(self):
        app = create_app(self.temp.name, api_key="test-only")
        catalog = app.extensions["catalog"]
        client = app.test_client()
        first = {"id": 197, "title": "Thanks to (EN Ver)", "album": "Thanks to"}
        catalog.merge([first])
        identity = next(c["id"] for c in catalog.view()["candidates"] if c["source_album"] == "Thanks to")
        prefix = f"/albums/{identity}"
        self.assertEqual(client.get(prefix + "/api/review").status_code, 200)
        release_store = Store(self.store.directory / "releases" / identity)
        release_store.update(lambda state: find_track(state, 197).update(publish_selected=True))
        catalog.merge([first | {"title": "Changed source title"}])
        state = client.get(prefix + "/api/review").get_json()
        self.assertFalse(find_track(state, 197)["publish_selected"])
        self.assertIn("pending_index", find_track(state, 197))
        # A rescan followed directly by Publish must synchronize even without a poll.
        catalog.merge([first | {"title": "Another change"}])
        release_store.update(lambda state: find_track(state, 197).update(publish_selected=True))
        with patch("service.ReviewService.start") as start:
            self.assertEqual(client.post(prefix + "/api/jobs/publish", json={}).status_code, 202)
        start.assert_called_once_with("publish")
        self.assertFalse(find_track(release_store.read(), 197)["publish_selected"])
        self.assertEqual(find_track(release_store.read(), 197)["pending_index"]["title"], "Another change")


if __name__ == "__main__":
    unittest.main()
