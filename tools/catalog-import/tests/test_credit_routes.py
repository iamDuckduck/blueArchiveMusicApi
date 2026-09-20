import tempfile
import unittest
from unittest.mock import patch

from app import create_app


class CreditRouteTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.app = create_app(self.directory.name, "http://127.0.0.1:18084", "server-only-test-key")
        self.client = self.app.test_client()

    def test_page_links_destination_but_never_exposes_key(self):
        response = self.client.get("/credits")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"http://127.0.0.1:18084", response.data)
        self.assertNotIn(b"server-only-test-key", response.data)
        self.assertIn(b"/credits", self.client.get("/catalog").data)

    def test_lookup_and_explicit_alias_edit_go_to_profile_not_local_draft(self):
        before = self.app.extensions["review_store"].view()["album"]["fields"]
        profile = {"id": 4, "name": "Character / Actor", "characterName": "Character", "voiceActorName": "Actor", "aliases": ["Alias"]}
        with patch("creditprofiles.CreditProfiles.search", return_value=[profile]) as search:
            self.assertEqual(self.client.get("/api/credits?query=Character").get_json(), {"profiles": [profile]})
        search.assert_called_once_with("Character")
        with patch("creditprofiles.CreditProfiles.get", return_value=profile) as get:
            self.assertEqual(self.client.get("/api/credits/4").get_json(), profile)
        get.assert_called_once_with(4)
        with patch("creditprofiles.CreditProfiles.save_aliases", return_value=profile) as save:
            self.assertEqual(self.client.put("/api/credits/4/aliases", json={"aliases": ["Alias"]}).get_json(), profile)
        save.assert_called_once_with(4, ["Alias"])
        self.assertEqual(self.app.extensions["review_store"].view()["album"]["fields"], before)

    def test_alias_edits_keep_local_origin_protection_and_reject_extra_fields(self):
        with patch("creditprofiles.CreditProfiles.save_aliases") as save:
            self.assertEqual(self.client.put("/api/credits/4/aliases", json={"aliases": []}, headers={"Origin": "https://untrusted.example"}).status_code, 403)
            self.assertEqual(self.client.put("/api/credits/4/aliases", json={"aliases": [], "name": "Rename"}).status_code, 400)
            self.assertEqual(self.client.put("/api/credits/4/aliases", data="aliases=x").status_code, 415)
        save.assert_not_called()

    def test_missing_configuration_is_an_error_not_a_silent_local_save(self):
        app = create_app(self.directory.name)
        result = app.test_client().put("/api/credits/4/aliases", json={"aliases": []})
        self.assertEqual(result.status_code, 400)
        self.assertIn("API key", result.get_json()["error"])


if __name__ == "__main__":
    unittest.main()
