"""Every workspace screen keeps the same destinations, including scoped reviews."""
from html.parser import HTMLParser
import tempfile
import unittest

from app import create_app


class SidebarLinks(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.inside = False
        self.links = []
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "aside" and attrs.get("class") == "sidebar":
            self.inside = True
        if self.inside and tag == "a":
            self.links.append({"href": attrs["href"], "current": attrs.get("aria-current"), "label": ""})

    def handle_data(self, data):
        if self.inside and self.links:
            self.links[-1]["label"] += data.strip()

    def handle_endtag(self, tag):
        if tag == "aside":
            self.inside = False


class NavigationTests(unittest.TestCase):
    def test_review_section_links_resolve_and_keep_safety_guidance(self):
        with tempfile.TemporaryDirectory() as directory:
            page = create_app(directory).test_client().get("/albums/veritas-vol-2/").get_data(as_text=True)
            self.assertIn('aria-label="Review sections"', page)
            self.assertNotIn('data-stage="scan"', page)
            for target in ["album", "prep-heading", "track-review", "publish-heading"]:
                self.assertIn(f'href="#{target}"', page)
                self.assertIn(f'id="{target}"', page)
            self.assertIn("Publishing changes the configured backend database and media destination.", page)
            self.assertIn("Save changes keeps your local draft. It does not publish.", page)
            self.assertIn("What does loading details do?", page)
            self.assertIn("What gets published?", page)

    def test_shared_links_and_current_location_on_all_pages(self):
        with tempfile.TemporaryDirectory() as directory:
            app = create_app(directory)
            client = app.test_client()
            catalog = app.extensions["catalog"]
            catalog.merge([{"id": 197, "title": "Thanks to EN", "album": "Thanks to"}])
            identity = catalog.view()["candidates"][0]["id"]
            catalog.open_review(identity)
            pages = [("/catalog", "/catalog", "page"), ("/credits", "/credits", "page"),
                     ("/albums/veritas-vol-2/", "/catalog", "location"),
                     (f"/albums/{identity}/", "/catalog", "location")]
            expected = [("/catalog", "Blue Archive Music"), ("/catalog", "Albums"),
                        ("/credits", "Credit aliases")]
            for url, current, kind in pages:
                with self.subTest(url=url):
                    response = client.get(url)
                    self.assertEqual(response.status_code, 200)
                    links = SidebarLinks(response.get_data(as_text=True)).links
                    self.assertEqual([(link["href"], link["label"]) for link in links], expected)
                    self.assertEqual([(link["href"], link["current"]) for link in links if link["current"]],
                                     [(current, kind)])
                    for href, _ in expected:
                        self.assertEqual(client.get(href).status_code, 200)


if __name__ == "__main__":
    unittest.main()
