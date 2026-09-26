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
        response = self.client.get("/api/catalog")
        self.assertEqual(response.status_code, 200)
        reviews = response.get_json()["reviews"]
        self.assertEqual(before, {path: path.read_bytes() for path in self.catalog.directory.rglob("*.sqlite3")})
        self.assertEqual({r["title"] for r in reviews}, {"Original sample", "My corrected collection"})
        self.assertEqual({r["id"] for r in reviews}, {"veritas-vol-2", identity})
        self.assertIn(f'/albums/{identity}/', [r["url"] for r in reviews])
        for review in reviews:
            self.assertEqual(self.client.get(review["url"]).status_code, 200)

    def test_navigation_does_not_treat_veritas_as_a_special_destination(self):
        for url in ["/catalog", "/credits", "/albums/veritas-vol-2/"]:
            page = self.client.get(url).get_data(as_text=True)
            self.assertIn('href="/catalog"', page)
            self.assertNotIn("Saved Veritas review", page)
        self.assertEqual(self.client.get("/albums/veritas-vol-2/").status_code, 200)

    def test_home_and_old_saved_reviews_bookmark_redirect_without_creating_drafts(self):
        before = {path: path.read_bytes() for path in self.catalog.directory.rglob("*.sqlite3")}
        for url, destination in [("/", "/catalog"), ("/reviews", "/catalog?view=saved")]:
            response = self.client.get(url)
            self.assertEqual(response.status_code, 302)
            self.assertEqual(response.headers["Location"], destination)
            self.assertEqual(self.client.get(destination).status_code, 200)
        self.assertEqual(before, {path: path.read_bytes() for path in self.catalog.directory.rglob("*.sqlite3")})


if __name__ == "__main__":
    unittest.main()
