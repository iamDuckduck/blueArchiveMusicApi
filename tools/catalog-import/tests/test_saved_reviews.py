import tempfile
import unittest

from app import create_app


class SavedReviewsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.app = create_app(self.temp.name)
        self.client = self.app.test_client()
        self.catalog = self.app.extensions["catalog"]
        self.sample = self.app.extensions["review_store"]

    def test_lists_saved_titles_and_original_sample_without_creating_other_reviews(self):
        self.catalog.merge([{"id": 197, "title": "Thanks to EN", "album": "Thanks to"},
                            {"id": 999, "title": "Another song", "album": "Not opened"}])
        identity = next(c["id"] for c in self.catalog.view()["candidates"] if c["source_album"] == "Thanks to")
        draft = self.catalog.open_review(identity)
        draft.update(lambda s: s["album"]["edits"].update(title="My corrected collection"))
        self.sample.update(lambda s: s["album"]["edits"].update(title="Original sample"))
        before = {path: path.read_bytes() for path in self.catalog.directory.rglob("*.sqlite3")}
        response = self.client.get("/reviews")
        self.assertEqual(response.status_code, 200)
        page = response.get_data(as_text=True)
        self.assertIn("Original sample", page)
        self.assertIn("My corrected collection", page)
        self.assertIn(f'/albums/{identity}/', page)
        self.assertNotIn("Not opened", page)
        self.assertEqual(before, {path: path.read_bytes() for path in self.catalog.directory.rglob("*.sqlite3")})

    def test_navigation_does_not_treat_veritas_as_a_special_destination(self):
        for url in ["/", "/catalog", "/reviews"]:
            page = self.client.get(url).get_data(as_text=True)
            self.assertIn('href="/reviews"', page)
            self.assertNotIn("Saved Veritas review", page)
        self.assertEqual(self.client.get("/albums/veritas-vol-2/").status_code, 200)


if __name__ == "__main__":
    unittest.main()
