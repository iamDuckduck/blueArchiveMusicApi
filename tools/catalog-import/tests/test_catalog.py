import tempfile
import unittest
import uuid
from unittest.mock import Mock, patch

from catalog import Catalog, fetch_index
from store import Store
from app import create_app


def track(identity, album="Official single", title="Music"):
    return {"id": identity, "album": album, "title": title, "author": "Evidence only"}


def page(number, rows):
    return Mock(status_code=200, json=lambda: {"success": True, "data": {"max_page": number, "music": rows}})


class DiscoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.catalog = Catalog(self.temp.name)

    def test_full_pagination_without_old_series_or_duration_filters(self):
        with patch("sources.requests.get", side_effect=[page(2, [track(1, "OST")]), page(2, [track(2, "New single")])]) as get:
            records = fetch_index()
        self.assertEqual([r["id"] for r in records], [1, 2])
        self.assertEqual(get.call_args_list[1].kwargs["params"], {"page": 2, "page_size": 100})

    def test_invalid_empty_repeated_or_changing_pages_fail_closed(self):
        for responses in [[page(1, [])], [page(2, [track(1)]), page(2, [track(1)])],
                          [page(2, [track(1)]), page(3, [track(2)])]]:
            with self.subTest(responses=responses), patch("sources.requests.get", side_effect=responses):
                with self.assertRaises(ValueError):
                    fetch_index()

    def test_decisions_and_ids_survive_unchanged_scan_and_restart(self):
        rows = [track(1), track(2, "Another release")]
        self.catalog.merge(rows)
        identity = next(iter(self.catalog.read()["candidates"]))
        self.catalog.decide(identity, "skipped")
        self.catalog.merge(rows)
        restarted = Catalog(self.temp.name).read()
        self.assertEqual(restarted["candidates"][identity]["decision"], "skipped")
        self.assertEqual(len(restarted["candidates"]), 2)
        self.assertEqual(len(restarted["snapshots"]), 1)

    def test_failed_scan_preserves_prior_candidates_and_decisions(self):
        self.catalog.merge([track(1)])
        before = self.catalog.read()["candidates"]
        with patch("catalog.fetch_index", side_effect=ValueError("Source unavailable")):
            self.catalog.start_scan()
            self.catalog.thread.join(3)
        result = self.catalog.read()
        self.assertEqual(result["candidates"], before)
        self.assertEqual(result["scan"]["status"], "failed")
        self.assertFalse(self.catalog.job_lock.locked())

    def test_changed_and_missing_entries_preserve_prior_raw_evidence(self):
        self.catalog.merge([track(1), track(2), track(3, "Other release")])
        identity = next(iter(self.catalog.read()["candidates"]))
        self.catalog.merge([track(1, title="New title"), track(4)])
        state = self.catalog.read()
        candidate = state["candidates"][identity]
        self.assertEqual(candidate["previous_records"], [track(1), track(2)])
        self.assertEqual(candidate["changes"], [{"id": 1, "change": "changed"}, {"id": 4, "change": "new"},
                                                {"id": 2, "change": "not_in_latest_index"}])
        self.assertEqual(len(state["candidates"]), 2)
        other = next(c for c in state["candidates"].values() if c["source_album"] == "Other release")
        self.assertFalse(other["seen_in_latest_scan"])
        self.assertEqual(other["records"], [track(3, "Other release")])

    def test_groupings_and_unknown_releases_cannot_be_included_as_albums(self):
        self.catalog.merge([track(1, "游戏内曲目"), track(2, "")])
        for identity in self.catalog.read()["candidates"]:
            with self.assertRaises(ValueError):
                self.catalog.decide(identity, "included")
        self.assertEqual(len(self.catalog.read()["candidates"]), 2)

    def test_scan_does_not_mutate_saved_veritas_review(self):
        store = Store(self.temp.name)
        store.save_edits({"album": {"title": "Owner correction"}})
        before = store.read()
        self.catalog.merge([track(255, before["album"]["suggestions"]["title"])])
        self.assertEqual(store.read(), before)
        self.assertIn("veritas-vol-2", self.catalog.read()["candidates"])

    def test_catalog_routes_share_local_request_protection_and_job_lock(self):
        app = create_app(self.temp.name)
        client = app.test_client()
        self.assertEqual(client.get("/catalog").status_code, 200)
        self.assertEqual(client.post("/api/catalog/scan", json={}, headers={"Origin": "https://foreign.example"}).status_code, 403)
        service = app.extensions["review_service"]
        service.job_lock.acquire()
        try:
            self.assertEqual(client.post("/api/catalog/scan", json={}).status_code, 400)
        finally:
            service.job_lock.release()

    def test_multiple_reviews_are_isolated_and_new_tracks_are_not_auto_selected(self):
        app = create_app(self.temp.name)
        catalog = app.extensions["catalog"]
        catalog.merge([track(81, "Release A"), track(82, "Release B")])
        identities = list(catalog.read()["candidates"])
        client = app.test_client()
        for identity in identities:
            self.assertEqual(client.get(f"/albums/{identity}/").status_code, 200)
        a, b = identities
        self.assertEqual(client.put(f"/albums/{a}/api/review", json={"album":{"title":"My correction"}}).status_code, 200)
        self.assertEqual(client.get(f"/albums/{a}/api/review").json["album"]["fields"]["title"], "My correction")
        other = client.get(f"/albums/{b}/api/review").json
        self.assertEqual(other["album"]["fields"]["title"], "Release B")
        self.assertFalse(other["tracks"][0]["included"])
        self.assertFalse(other["tracks"][0]["publish_selected"])
        self.assertEqual(other["album"]["fields"]["gamekee_url"], "")
        catalog.merge([track(81, "Release A", "Source edit"), track(83, "Release A"), track(82, "Release B")])
        client.get(f"/albums/{a}/")
        saved = client.get(f"/albums/{a}/api/review").json
        self.assertEqual(saved["album"]["fields"]["title"], "My correction")
        self.assertEqual(saved["tracks"][0]["fields"]["title"], "Music")
        self.assertEqual(saved["tracks"][0]["pending_index"]["title"], "Source edit")
        self.assertFalse(saved["tracks"][1]["included"])
        self.assertEqual(len(saved["tracks"]), 2)
        restarted = create_app(self.temp.name).test_client()
        self.assertEqual(restarted.get(f"/albums/{a}/api/review").json["album"]["fields"]["title"], "My correction")

    def test_explicit_drama_is_excluded_without_a_duration_heuristic(self):
        self.catalog.merge([track(1, title="ボイスドラマ bonus"), track(2, title="Music (Instrumental Ver.)")])
        identity = next(iter(self.catalog.read()["candidates"]))
        review = self.catalog.open_review(identity).view()
        self.assertEqual(review["tracks"][0]["fields"]["kind"], "drama")
        self.assertFalse(review["tracks"][0]["included"])
        self.assertEqual(review["tracks"][1]["fields"]["kind"], "instrumental")

    def test_new_tracks_append_after_reviewed_display_order_without_fabricating_numbering(self):
        self.catalog.merge([track(1)])
        identity = next(iter(self.catalog.read()["candidates"]))
        self.catalog.open_review(identity).save_edits({"tracks":{"1":{"display_order":20}}})
        self.catalog.merge([track(1), track(2)])
        saved = self.catalog.open_review(identity).view()
        self.assertEqual(saved["tracks"][1]["fields"]["display_order"], 21)
        self.assertIsNone(saved["tracks"][1]["fields"]["position"])
        self.assertIsNone(saved["tracks"][1]["fields"]["disc"])

    def test_saved_discovery_decision_applies_when_reopening_an_existing_review(self):
        self.catalog.merge([track(1)])
        identity = next(iter(self.catalog.read()["candidates"]))
        self.catalog.decide(identity, "included")
        self.assertEqual(self.catalog.open_review(identity).read()["album"]["decision"], "included")
        self.catalog.decide(identity, "skipped")
        restarted = Catalog(self.temp.name)
        self.assertEqual(restarted.open_review(identity).read()["album"]["decision"], "skipped")

    def test_grouped_tracks_can_map_to_two_official_appearances_without_reclassifying_source(self):
        self.catalog.merge([track(1, "游戏内曲目"), track(2, "游戏内曲目")])
        source = next(iter(self.catalog.read()["candidates"]))
        targets = [str(uuid.uuid4()), str(uuid.uuid4())]
        for identity in targets:
            fields = {"id":identity, "title":"Official OST " + identity[:4], "category":"OST", "official":True}
            self.catalog.create_release(fields)
            self.catalog.create_release(fields)  # Lost response retry does not create another release.
            self.catalog.map_tracks(source, identity, [1])
            self.catalog.map_tracks(source, identity, [1])
            saved = self.catalog.open_review(identity).view()
            self.assertEqual(len(saved["tracks"]), 1)
            self.assertEqual(saved["tracks"][0]["source_id"], 1)
            self.assertFalse(saved["tracks"][0]["included"])
            self.assertFalse(saved["tracks"][0]["publish_selected"])
        self.assertEqual(len(self.catalog.read()["candidates"]), 3)
        self.assertEqual(self.catalog.read()["candidates"][source]["kind"], "source_grouping")
        self.catalog.merge([track(1, "游戏内曲目", "Changed source"), track(2, "游戏内曲目")])
        changed = self.catalog.open_review(targets[0]).view()["tracks"][0]
        self.assertEqual(changed["fields"]["title"], "Music")
        self.assertEqual(changed["pending_index"]["title"], "Changed source")

    def test_renamed_label_links_into_existing_review_without_changing_ids_or_edits(self):
        self.catalog.merge([track(1, "Old label")])
        target = next(iter(self.catalog.read()["candidates"]))
        saved = self.catalog.open_review(target)
        saved.save_edits({"album":{"title":"Reviewed official title"}})
        saved.update(lambda s: s["publication"].update(album={"albumId":42}))
        self.catalog.merge([track(1, "New label")])
        source = next(i for i in self.catalog.read()["candidates"] if i != target)
        self.catalog.link_release(source, target)
        self.catalog.merge([track(1, "New label")])
        result = self.catalog.open_review(target).view()
        self.assertEqual(result["album"]["id"], target)
        self.assertEqual(result["album"]["fields"]["title"], "Reviewed official title")
        self.assertEqual(result["publication"]["album"]["albumId"], 42)
        self.assertEqual(len(result["tracks"]), 1)
        self.assertEqual(self.catalog.read()["candidates"][source]["redirect_to"], target)
        with self.assertRaises(ValueError):
            self.catalog.decide(source, "included")
        with self.assertRaises(ValueError):
            self.catalog.open_review(source)

    def test_missing_mapped_and_whole_release_records_warn_without_losing_review(self):
        self.catalog.merge([track(1, "Source"), track(2, "Other")])
        source, other = self.catalog.read()["candidates"]
        self.catalog.map_tracks(source, other, [1])
        for identity in [source, other]:
            self.catalog.open_review(identity).save_edits({"tracks":{"1":{"notes":"Keep correction"}}})
        self.catalog.merge([track(2, "Other")])
        for identity in [source, other]:
            saved = self.catalog.open_review(identity).view()
            row = next(t for t in saved["tracks"] if t["source_id"] == 1)
            self.assertTrue(row["missing_index"])
            self.assertEqual(row["fields"]["notes"], "Keep correction")
        self.catalog.merge([track(1, "Source"), track(2, "Other")])
        returned = self.catalog.open_review(other).view()
        self.assertFalse(next(t for t in returned["tracks"] if t["source_id"] == 1).get("missing_index"))

    def test_invalid_mapping_targets_are_client_errors(self):
        app = create_app(self.temp.name)
        catalog = app.extensions["catalog"]
        catalog.merge([track(1)])
        identity = next(iter(catalog.read()["candidates"]))
        for action in ["map", "link"]:
            result = app.test_client().post(f"/api/catalog/{identity}/{action}", json={"target":[], "track_ids":[1]})
            self.assertEqual(result.status_code, 400)

    def test_mapping_rejects_unknown_tracks_and_linking_never_discards_an_existing_review(self):
        self.catalog.merge([track(1, "A"), track(2, "B")])
        a, b = self.catalog.read()["candidates"]
        with self.assertRaises(ValueError):
            self.catalog.map_tracks(a, b, [99])
        review = self.catalog.open_review(a)
        review.save_edits({"tracks":{"1":{"notes":"Keep this"}}})
        with self.assertRaises(ValueError):
            self.catalog.link_release(a, b)
        self.assertEqual(review.view()["tracks"][0]["fields"]["notes"], "Keep this")


if __name__ == "__main__":
    unittest.main()
